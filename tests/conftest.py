import sys
import types
import pytest

@pytest.fixture(autouse=True)
def mock_speechsdk(monkeypatch):
    """Provide a fake azure speech sdk for tests."""
    fake_sdk = types.SimpleNamespace()

    class FakeFuture:
        def __init__(self, result=None):
            self._result = result
        def get(self):
            return self._result

    class FakeEvent:
        def __init__(self):
            self._callbacks = []
        def connect(self, cb):
            self._callbacks.append(cb)
        def fire(self, evt=None):
            for cb in list(self._callbacks):
                cb(evt)

    class PropertyId:
        SpeechServiceConnection_EndSilenceTimeoutMs = 1
        Speech_SegmentationSilenceTimeoutMs = 2

    class ResultReason:
        RecognizedSpeech = 1

    class CancellationReason:
        Error = 1
        EndOfStream = 2
        CancelledByUser = 3

    class SpeechRecognitionResult:
        def __init__(self, text, reason):
            self.text = text
            self.reason = reason

    class SpeechConfig:
        def __init__(self, subscription=None, region=None):
            self.subscription = subscription
            self.region = region
            self.properties = {}
            self.speech_synthesis_voice_name = ""
        def set_property(self, prop_id, value):
            self.properties[prop_id] = value

    class AudioOutputConfig:
        def __init__(self, device_name=None):
            self.device_name = device_name

    class AudioConfig:
        def __init__(self, stream=None, device_name=None):
            self.stream = stream
            self.device_name = device_name

    class PushAudioInputStream:
        def write(self, data):
            pass

    class SpeechSynthesizer:
        spoken_texts = []
        def __init__(self, speech_config=None, audio_config=None):
            self.speech_config = speech_config
            self.audio_config = audio_config
            self.synthesis_completed = FakeEvent()
            self.synthesis_canceled = FakeEvent()
        def speak_text_async(self, text):
            self.__class__.spoken_texts.append(text)
            self.synthesis_completed.fire(types.SimpleNamespace())
        def stop_speaking_async(self):
            return FakeFuture()

    class KeywordRecognizer:
        """Fake keyword recognizer that exposes the last created instance."""

        last_instance = None

        def __init__(self, audio_config=None):
            self.audio_config = audio_config
            self.recognized = FakeEvent()
            self.canceled = FakeEvent()
            KeywordRecognizer.last_instance = self

        def recognize_once_async(self, model=None):
            self.model = model
            return FakeFuture()

        def stop_recognition_async(self):
            evt = types.SimpleNamespace(
                cancellation_details=types.SimpleNamespace(
                    reason=CancellationReason.EndOfStream
                )
            )
            self.canceled.fire(evt)
            return FakeFuture()

        def fire_recognized(self):
            evt = types.SimpleNamespace(result=types.SimpleNamespace(text="keyword"))
            self.recognized.fire(evt)

    class KeywordRecognitionModel:
        def __init__(self, path):
            self.path = path

    class SpeechRecognizer:
        next_result_text = "text"
        next_result_reason = ResultReason.RecognizedSpeech
        def __init__(self, speech_config=None, audio_config=None):
            self.speech_config = speech_config
            self.audio_config = audio_config
        def recognize_once_async(self):
            result = SpeechRecognitionResult(self.__class__.next_result_text,
                                              self.__class__.next_result_reason)
            return FakeFuture(result)

    audio = types.SimpleNamespace(
        AudioOutputConfig=AudioOutputConfig,
        AudioConfig=AudioConfig,
        PushAudioInputStream=PushAudioInputStream,
    )

    fake_sdk.SpeechConfig = SpeechConfig
    fake_sdk.SpeechSynthesizer = SpeechSynthesizer
    fake_sdk.KeywordRecognizer = KeywordRecognizer
    fake_sdk.KeywordRecognitionModel = KeywordRecognitionModel
    fake_sdk.SpeechRecognizer = SpeechRecognizer
    fake_sdk.SpeechRecognitionResult = SpeechRecognitionResult
    fake_sdk.PropertyId = PropertyId
    fake_sdk.ResultReason = ResultReason
    fake_sdk.CancellationReason = CancellationReason
    fake_sdk.audio = audio

    module = types.ModuleType("azure.cognitiveservices.speech")
    for name, value in fake_sdk.__dict__.items():
        setattr(module, name, value)

    azure = types.ModuleType("azure")
    cognitiveservices = types.ModuleType("azure.cognitiveservices")
    azure.cognitiveservices = cognitiveservices
    cognitiveservices.speech = module

    sys.modules["azure"] = azure
    sys.modules["azure.cognitiveservices"] = cognitiveservices
    sys.modules["azure.cognitiveservices.speech"] = module

    yield fake_sdk

@pytest.fixture(autouse=True)
def mock_sounddevice(monkeypatch):
    fake_sd = types.SimpleNamespace()

    def query_devices():
        return [
            {"name": "Fake Output (plughw:1,0)", "max_output_channels": 2, "max_input_channels": 0},
            {"name": "Fake Input", "max_output_channels": 0, "max_input_channels": 1},
        ]

    class InputStream:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    fake_sd.query_devices = query_devices
    fake_sd.InputStream = InputStream

    sys.modules["sounddevice"] = fake_sd

    yield fake_sd
