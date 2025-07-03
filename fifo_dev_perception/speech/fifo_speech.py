from __future__ import annotations
import multiprocessing
import queue
import re
import os
import threading
import logging
import uuid
from typing import Any, cast, TYPE_CHECKING
import azure.cognitiveservices.speech as speechsdk   # type: ignore  # No type stubs available

if TYPE_CHECKING:
    from multiprocessing import Queue as TypedQueue
    from multiprocessing.synchronize import Event as MpEvent
    TTSQueue = TypedQueue[tuple[str, str] | None]
else:
    TTSQueue = multiprocessing.Queue
    MpEvent = multiprocessing.Event

logger = logging.getLogger("FifoSpeech")

class FifoSpeechCallback:
    """
    Abstract callback interface for handling speech-related events.

    Implement this interface to receive events when a wake word is detected
    or when full speech text has been recognized.
    """

    def on_stt_keyword_recognized(self, keyword: str, speech: FifoSpeech):
        """
        Called when the wake word is detected.

        Args:
            keyword (str):
                The keyword that was detected (as recognized by Azure).

            speech (FifoSpeech):
                The FifoSpeech instance triggering the callback.
        """

    def on_stt_text_recognized(self, text: str, speech: FifoSpeech):
        """
        Called when full text has been recognized after wake word activation.

        Args:
            text (str):
                The full recognized speech-to-text output.

            speech (FifoSpeech):
                The FifoSpeech instance triggering the callback.
        """

    def on_tts_synthesis_done(self, request_id: str, success: bool):
        """
        Called when a TTS request has finished playback.

        Args:
            request_id (str):
                The unique ID assigned to the TTS request when it was enqueued.

            success (bool):
                True if playback completed successfully; False otherwise.
        """

class FifoSpeech:
    """
    Manages speech input and output using Azure Cognitive Services.

    This class spawns two processes:
      - A background loop for wake word detection and speech-to-text conversion.
      - A background loop for text-to-speech playback.

    Wake word detection is performed locally using a .table model, and speech recognition is
    cloud-based. Text-to-speech output is queued and played in sequence, with an optional immediate
    flag to interrupt the queue.

    Parameters:
        wake_word_model (str):
            Path to the .table model file used for offline keyword spotting.

        callback (FifoSpeechCallback):
            An instance that receives events when a keyword is detected or speech is recognized.

        microphone (str):
            Substring of the user-friendly input device name as reported by
            `sounddevice.query_devices()` (e.g., "C922 Pro Stream Webcam" or any USB microphone
            device name). The substring must uniquely identify an input device with at least one
            input channel.

        speaker (str):
            Substring of the user-friendly output device name as reported by
            `sounddevice.query_devices()` (e.g., "USB Audio").
            The substring must uniquely identify an output device with at least one output channel.
            The ALSA device name (e.g., "plughw:1,0") is extracted automatically from the match
            and passed to `AudioOutputConfig(device_name=...)`.

        voice_name (str):
            Voice name to use for speech synthesis (e.g., "en-US-AvaMultilingualNeural").
            See the official Microsoft voice gallery for the full list:
            https://speech.microsoft.com/portal/voicegallery

        azure_key_env_var (str):
            Name of the environment variable that holds the Azure Speech API subscription key
            (e.g., "AZURE_SPEECH_KEY").
            The key must never be hardcoded in source code.

        azure_region (str):
            Azure service region (e.g., "westus2").
    """

    def __init__(self,
                wake_word_model: str,
                callback: FifoSpeechCallback,
                microphone: str,
                speaker: str,
                voice_name: str,
                azure_key_env_var: str,
                azure_region: str):
        """
        Initializes the FifoSpeech instance.

        Args:
            wake_word_model (str):
                Path to the .table model file used for offline keyword spotting.

            callback (FifoSpeechCallback):
                An instance that receives events when a keyword is detected or speech is recognized.

            microphone (str):
                Substring of the user-friendly input device name as reported by
                `sounddevice.query_devices()`. The substring must uniquely identify an
                input device with at least one input channel.

            speaker (str):
                Substring of the user-friendly output device name as reported by
                `sounddevice.query_devices()`. The substring must uniquely identify an
                output device with at least one output channel. The ALSA device name is
                extracted automatically from the match.

            voice_name (str):
                Voice name to use for speech synthesis (e.g., "en-US-AvaMultilingualNeural").

            azure_key_env_var (str):
                Name of the environment variable that holds the Azure Speech API subscription key.

            azure_region (str):
                Azure service region (e.g., "westus2").
        """
        logger.debug("[Init] Initializing FifoSpeech")
        self._wake_word_model_path = wake_word_model
        self._callback = callback
        self._microphone = microphone
        self._speaker = speaker
        self._voice_name = voice_name
        self._azure_key_env_var = azure_key_env_var
        self._azure_region = azure_region

        self._tts_queue: TTSQueue = multiprocessing.Queue()
        self._stt_stop_event: MpEvent = multiprocessing.Event()
        self._stt_keyword_done_event: MpEvent = multiprocessing.Event()
        self._tts_stop_event: MpEvent = multiprocessing.Event()
        self._tts_interrupt_event: MpEvent = multiprocessing.Event()

        self._tts_proc = multiprocessing.Process(
            target=self._tts_loop,
            args=(self._tts_interrupt_event, self._tts_stop_event)
        )
        self._stt_proc = multiprocessing.Process(
            target=self._stt_loop,
            args=(self._stt_stop_event, self._stt_keyword_done_event)
        )

    def start(self):
        """
        Start the background processes for text-to-speech and speech-to-text.
        """
        logger.debug("[Core] Starting TTS and STT processes")
        self._tts_proc.start()
        self._stt_proc.start()

    def stop(self):
        """
        Stop the background processes by signaling termination and sending
        a sentinel value to the TTS queue.
        """
        logger.debug("[Core] Stopping TTS and STT processes")
        self._stt_stop_event.set()
        self._tts_stop_event.set()
        self._tts_interrupt_event.set()
        self._tts_queue.put(None)

    def join(self):
        """
        Wait for the background processes to terminate.
        """
        logger.debug("[Core] Joining TTS and STT processes")
        self._tts_proc.join()
        self._stt_proc.join()
        logger.debug("[Core] Processes joined")

    def text_to_speech(self, text: str, immediate: bool) -> str:
        """
        Add text to the TTS queue for playback and return the request ID.

        Args:
            text (str):
                The text to be synthesized and spoken.

            immediate (bool):
                If True, clears the current queue before speaking this text.
        """
        request_id = str(uuid.uuid4())

        if immediate:
            logger.debug("[TTS] Immediate text requested")
            self._tts_interrupt_event.set()
            while True:
                try:
                    self._tts_queue.get_nowait()
                except queue.Empty:
                    break
        else:
            logger.debug("[TTS] Queued text")
        self._tts_queue.put((request_id, text))
        return request_id

    def _get_azure_key(self) -> str:
        """
        Retrieve the Azure Speech API key from the environment.

        Returns:
            str:
                The Azure API key retrieved from the environment variable specified by
                `self._azure_key_env_var`.

        Raises:
            RuntimeError:
                If the environment variable is not set or is empty.

                This method does not expose the variable name or value in the error message
                to avoid accidental secret leakage.
        """
        azure_key = os.environ.get(self._azure_key_env_var)
        if not azure_key:
            raise RuntimeError("Azure Speech API key is not configured in the environment.")
        return azure_key

    def stt_skip_keyword_detection(self) -> None:
        """
        Signal the STT loop to skip waiting for keyword detection.

        This sets the shared `keyword_done_event`, allowing the STT process to bypass
        the keyword detection step and proceed immediately to speech recognition. This is useful
        for enabling faster back-and-forth conversations without requiring a wake word each time.
        """
        logger.debug("[STT] Skip keyword detection")
        self._stt_keyword_done_event.set()

    def _tts_loop(self, interrupt_event: MpEvent, stop_event: MpEvent):
        """
        Internal method that runs in a separate process to handle TTS playback.
        Launches a thread for speech synthesis that can be interrupted asynchronously.

        Args:
            stop_event (multiprocessing.Event):
                Shared stop event used to exit the loop cleanly.

            interrupt_event (multiprocessing.Event):
                Shared event used to interrupt and cancel the current text-to-speech playback.
                When set, the ongoing synthesis is stopped and the next item in the queue is
                processed immediately.
        """
        logger.debug("[TTS] Loop started")
        # Importing sounddevice inside _tts_loop ensures that PortAudio initializes
        # correctly in the child process. Importing it at the module level can cause
        # PortAudio to break across process boundaries (e.g., with multiprocessing),
        # leading to errors like: PaErrorCode -9993.
        import sounddevice as sd  # type: ignore  # pylint: disable=import-outside-toplevel

        def get_output_alsa_device_name(name_substring: str) -> str:
            """
            Map a user-friendly output device name substring to an ALSA device string usable with
            `AudioOutputConfig`.

            Args:
                name_substring (str):
                    Substring of the user-friendly output device name as reported by
                    `sounddevice.query_devices()` (e.g., "USB Audio").
                    The substring must uniquely identify an output device with at least one output
                    channel.

            Returns:
                str:
                    ALSA device name in the form "plughw:X,Y" (e.g., "plughw:1,0").
                    If the matched device reports "hw:X,Y", it is automatically converted to
                    "plughw:X,Y".

            Raises:
                ValueError:
                    If no matching output device is found or if multiple matches are found.
            """
            name_substring = name_substring.lower()
            matches: list[str] = []

            for dev in cast(
                list[dict[str, Any]],
                # Pylance: Type of "query_devices" is partially unknown
                sd.query_devices()  # type: ignore[reportUnknownMemberType]
            ):
                if dev['max_output_channels'] > 0 and name_substring in dev['name'].lower():
                    # Try to extract ALSA part: (plughw:1,0) or (hw:1,0)
                    match = re.search(r"\((plughw:\d+,\d+|hw:\d+,\d+)\)", dev['name'])
                    if match:
                        alsa_name = match.group(1)
                        if alsa_name.startswith("hw:"):
                            alsa_name = f"plug{alsa_name}"
                        matches.append(alsa_name)

            if not matches:
                raise ValueError(
                    f"No ALSA-compatible output device found matching: '{name_substring}'"
                )
            if len(matches) > 1:
                raise ValueError(
                    f"Multiple output devices match '{name_substring}': {matches}"
                )

            return matches[0]

        speech_config = speechsdk.SpeechConfig(
            subscription=self._get_azure_key(), region=self._azure_region
        )
        audio_config = speechsdk.audio.AudioOutputConfig(
            device_name=get_output_alsa_device_name(self._speaker)
        )
        speech_config.speech_synthesis_voice_name = self._voice_name
        synthesizer = speechsdk.SpeechSynthesizer(speech_config, audio_config)

        done = threading.Event()
        synthesis_success = True

        def on_completed(_evt: Any):
            nonlocal synthesis_success
            logger.debug("[TTS] Synthesis completed")
            synthesis_success = True
            done.set()

        def on_canceled(_evt: Any):
            nonlocal synthesis_success
            logger.debug("[TTS] Synthesis canceled")
            synthesis_success = False
            done.set()

        # Pylance: Type of "connect" is partially unknown
        synthesizer.synthesis_completed.connect(on_completed)# type: ignore[reportUnknownMemberType]
        synthesizer.synthesis_canceled.connect(on_canceled)  # type: ignore[reportUnknownMemberType]

        def speak_loop():
            logger.debug("[TTS] Speak thread started")
            while True:
                item = self._tts_queue.get()
                if item is None:
                    logger.debug("[TTS] Exiting speak_loop")
                    break
                request_id, text = item
                logger.debug("[TTS] Speaking")
                done.clear()
                synthesizer.speak_text_async(text)
                done.wait()
                self._callback.on_tts_synthesis_done(request_id, synthesis_success)
            logger.debug("[TTS] Speak thread finished")

        thread = threading.Thread(target=speak_loop, daemon=True)
        thread.start()

        while not stop_event.is_set():
            if interrupt_event.wait():
                interrupt_event.clear()
                logger.debug("[TTS] Interrupt received, stopping current speech")
                synthesizer.stop_speaking_async().get()
                synthesis_success = False
                done.set()

        logger.debug("[TTS] Waiting for speak thread to exit")
        thread.join()
        logger.debug("[TTS] TTS loop exited")

    def _stt_loop(self, stop_event: MpEvent, keyword_done_event: MpEvent):
        """
        Internal method that runs in a separate process to perform
        wake word detection followed by speech recognition.
        Calls the callback on detection and recognition events.

        Args:
            stop_event (multiprocessing.Event):
                Shared stop event used to exit the loop cleanly.
            
            keyword_done_event (multiprocessing.Event):
                Shared event used to signal that keyword detection has completed or should be
                aborted. This is used to end the wait on `recognize_once_async` once a keyword is
                detected, should be skipped or external shutdown is requested.
        """
        logger.debug("[STT] Loop started")
        # Importing sounddevice inside _stt_loop ensures that PortAudio initializes
        # correctly in the child process. Importing it at the module level can cause
        # PortAudio to break across process boundaries (e.g., with multiprocessing),
        # leading to errors like: PaErrorCode -9993.
        import sounddevice as sd  # type: ignore  # pylint: disable=import-outside-toplevel

        def get_input_device_index(name_substring: str) -> int:
            """
            Return the index of the input device matching the given name substring.

            Args:
                name_substring (str):
                    Substring of the user-friendly input device name as reported by
                    `sounddevice.query_devices()` (e.g., "C922 Pro Stream Webcam").
                    The substring must uniquely identify an input device with at least
                    one input channel.

            Returns:
                int:
                    The device index suitable for use with `sounddevice.InputStream`.

            Raises:
                ValueError:
                    If no matching input device is found or if multiple matches exist.
            """
            name_substring = name_substring.lower()
            matches: list[tuple[int, str]] = []

            for i, dev in enumerate(
                cast(
                    list[dict[str, Any]],
                    # Pylance: Type of "query_devices" is partially unknown
                    sd.query_devices()  # type: ignore[reportUnknownMemberType]
                )
            ):
                if dev['max_input_channels'] > 0 and name_substring in dev['name'].lower():
                    matches.append((i, dev['name']))

            if not matches:
                raise ValueError(f"No input device found matching: '{name_substring}'")
            if len(matches) > 1:
                options = ", ".join(f"[{i}] {name}" for i, name in matches)
                raise ValueError(f"Multiple input devices match '{name_substring}': {options}")

            return matches[0][0]

        def keyword_loop() -> None:
            logger.debug("[STT] Keyword loop started")

            # The KeywordRecognizer fires a Canceled event both for errors and
            # when we manually stop recognition. We use the event's
            # CancellationReason to differentiate between the two cases.

            stream = speechsdk.audio.PushAudioInputStream()
            audio_config = speechsdk.audio.AudioConfig(stream=stream)
            speech_config = speechsdk.SpeechConfig(subscription=self._get_azure_key(),
                                                   region=self._azure_region)
            speech_config.set_property(
                speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "250"
            )
            speech_config.set_property(
                speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs, "250"
            )

            keyword_model = speechsdk.KeywordRecognitionModel(self._wake_word_model_path)
            keyword_recognizer = speechsdk.KeywordRecognizer(audio_config=audio_config)
            speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config,
                                                           audio_config=audio_config)

            def callback(indata: Any, _frames: Any, _time: Any, status: Any):
                if status:
                    logger.warning("[STT] Audio warning: %s", status)
                stream.write(indata.tobytes())

            def recognized_cb(evt: Any):
                logger.debug("[STT] Keyword detected")
                self._callback.on_stt_keyword_recognized(evt.result.text, self)
                keyword_done_event.set()

            def canceled_cb(evt: Any):
                logger.debug("[STT] Keyword recognition canceled")
                reason = getattr(getattr(evt, "cancellation_details", None),
                                 "reason",
                                 None)
                if reason != speechsdk.CancellationReason.CancelledByUser:
                    keyword_done_event.set()

            # Pylance: Type of "connect" is partially unknown
            keyword_recognizer.recognized.connect( # type: ignore[reportUnknownMemberType]
                recognized_cb
            )
            keyword_recognizer.canceled.connect( # type: ignore[reportUnknownMemberType]
                canceled_cb
            )

            audio_capture_loop_event = threading.Event()

            def audio_capture_loop() -> None:
                logger.debug("[STT] Audio input stream started")
                with sd.InputStream(device=get_input_device_index(self._microphone),
                                    samplerate=16000,
                                    channels=1,
                                    dtype='int16',
                                    callback=callback):
                    audio_capture_loop_event.wait()
                logger.debug("[STT] Audio input stream exiting")

            audio_thread = threading.Thread(target=audio_capture_loop, daemon=True)
            audio_thread.start()

            while not stop_event.is_set():
                if keyword_done_event.is_set():
                    logger.debug("[STT] Skip signal already set, skipping keyword detection")
                else:
                    logger.debug("[STT] Waiting for keyword")
                    keyword_done_event.clear()  # Safe: we are about to wait
                    keyword_recognizer.recognize_once_async(keyword_model)
                    keyword_done_event.wait()
                    logger.debug("[STT] Keyword triggered, stopping keyword recognizer")
                    keyword_recognizer.stop_recognition_async().get()

                keyword_done_event.clear()
                if stop_event.is_set():
                    break

                logger.debug("[STT] Starting speech recognition")
                result = cast(
                    speechsdk.SpeechRecognitionResult,
                    speech_recognizer.recognize_once_async().get()
                )
                if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    logger.debug("[STT] Recognized text")
                    self._callback.on_stt_text_recognized(result.text, self)

            logger.debug("[STT] Ending keyword loop")
            audio_capture_loop_event.set()

        logger.debug("[STT] Starting keyword thread")
        keyword_thread = threading.Thread(target=keyword_loop, daemon=True)
        keyword_thread.start()

        stop_event.wait()
        logger.debug("[STT] Stop event received, exiting STT loop")
        keyword_done_event.set()
        keyword_thread.join()
        logger.debug("[STT] STT thread exited")
