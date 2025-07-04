from __future__ import annotations
import os
import sys
import time
import queue
import threading
import importlib
import multiprocessing
import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING
import pytest


# Disable protected-access warning: we need to test and inspect internal state and behavior
# of the class under test (`FifoSpeech`). Accessing protected members is necessary in this context.
# pylint: disable=protected-access


def load_module():
    """
    Reload the fifo_speech module so it picks up mocked dependencies like `speechsdk`.
    Required because `speechsdk` is imported at module level in fifo_speech.py.
    """
    import fifo_dev_perception.speech.fifo_speech as mod
    return importlib.reload(mod)


if TYPE_CHECKING:
    from multiprocessing import Queue as TypedQueue
    from fifo_dev_perception.speech.fifo_speech import (
        FifoSpeech,
        FifoSpeechCallback,
    )
    DummyCallbackBase = FifoSpeechCallback
    MPQueue = TypedQueue[tuple[str, str] | None]
else:
    DummyCallbackBase = load_module().FifoSpeechCallback
    MPQueue = multiprocessing.Queue


class DummyCallback(DummyCallbackBase):

    def __init__(self) -> None:
        self.keywords: list[str] = []
        self.texts: list[str] = []
        self.tts: list[tuple[str, bool]] = []

    def on_stt_keyword_recognized(self, keyword: str, speech: FifoSpeech):
        self.keywords.append(keyword)

    def on_stt_text_recognized(self, text: str, speech: FifoSpeech):
        self.texts.append(text)

    def on_tts_synthesis_done(self, request_id: str, success: bool):
        self.tts.append((request_id, success))


def drain_queue(q: MPQueue) -> list[tuple[str, str] | None]:
    """
    Drain all available items from a multiprocessing.Queue into a list.

    This function non-blockingly retrieves and removes all items currently
    in the queue using `get_nowait()`. It is useful in test environments,
    especially when comparing actual queue contents against expected ones.

    Args:
        q (multiprocessing.Queue):
            The multiprocessing queue to drain.

    Returns:
        list[str | None]:
            A list containing all items that were in the queue.
    """
    result: list[tuple[str, str] | None] = []
    try:
        while True:
            result.append(q.get_nowait())
    except queue.Empty:
        pass
    return result


def make_speech(tmp_key_env: str="AZ_KEY") -> tuple[FifoSpeech, DummyCallback]:
    mod = load_module()
    os.environ[tmp_key_env] = "secret"
    cb = DummyCallback()
    fs = mod.FifoSpeech(
        wake_word_model="model.table",
        callback=cb,
        microphone="Fake Input",
        speaker="Fake Output",
        voice_name="voice",
        azure_key_env_var=tmp_key_env,
        azure_region="region",
    )
    return fs, cb


def test_get_azure_key_success():
    fs, _ = make_speech()
    assert fs._get_azure_key() == "secret"  # pyright: ignore[reportPrivateUsage]


def test_get_azure_key_missing():
    fs, _ = make_speech("MISSING")
    if "MISSING" in os.environ:
        del os.environ["MISSING"]
    with pytest.raises(RuntimeError):
        fs._get_azure_key()  # pyright: ignore[reportPrivateUsage]


def test_text_to_speech_queue_immediate():
    fs, _ = make_speech()
    fs._tts_queue = multiprocessing.Queue()  # pyright: ignore[reportPrivateUsage]

    fs.text_to_speech("first", False)

    # Wait for the feeder thread to flush the first queued item (non-immediate)
    time.sleep(0.05)

    req2 = fs.text_to_speech("second", True)

    # Wait for the immediate TTS item ("second") to be enqueued before draining
    time.sleep(0.05)

    assert fs._tts_interrupt_event.is_set()  # pyright: ignore[reportPrivateUsage]
    assert list(drain_queue(fs._tts_queue)) == [(req2, "second")]  # pyright: ignore[reportPrivateUsage]


def test_stt_skip_keyword_detection_sets_event():
    fs, _ = make_speech()
    fs.stt_skip_keyword_detection()
    assert fs._stt_keyword_done_event.is_set()  # pyright: ignore[reportPrivateUsage]


def test_tts_loop_runs_and_speaks(mock_speechsdk: SimpleNamespace):
    fs, cb = make_speech()
    fs._tts_queue = multiprocessing.Queue()  # pyright: ignore[reportPrivateUsage]
    req_id = str(uuid.uuid4())
    fs._tts_queue.put((req_id, "hello"))  # pyright: ignore[reportPrivateUsage]
    fs._tts_queue.put(None)  # pyright: ignore[reportPrivateUsage]
    interrupt = threading.Event()
    stop = threading.Event()
    thread = threading.Thread(
        target=fs._tts_loop,  # pyright: ignore[reportPrivateUsage]
        args=(interrupt, stop)
    )
    thread.start()
    time.sleep(0.05)
    stop.set()
    interrupt.set()
    thread.join(timeout=1)
    assert "hello" in mock_speechsdk.SpeechSynthesizer.spoken_texts
    assert cb.tts == [(req_id, True)]


def test_stt_loop_detects_and_recognizes(mock_speechsdk: SimpleNamespace):
    fs, cb = make_speech()
    stop = threading.Event()
    done = threading.Event()
    thread = threading.Thread(
        target=fs._stt_loop,  # pyright: ignore[reportPrivateUsage]
        args=(stop, done)
    )
    thread.start()
    time.sleep(0.05)
    # Simulate wake word detection
    mock_speechsdk.KeywordRecognizer.last_instance.fire_recognized()
    time.sleep(0.05)
    stop.set()
    done.set()
    thread.join(timeout=1)
    assert cb.keywords == ["keyword"]
    assert cb.texts == [mock_speechsdk.SpeechRecognizer.next_result_text]


def test_skip_during_wait_does_not_skip_next_iteration(mock_speechsdk: SimpleNamespace):
    fs, cb = make_speech()
    stop = threading.Event()
    done = fs._stt_keyword_done_event  # pyright: ignore[reportPrivateUsage]
    done.clear()
    thread = threading.Thread(
        target=fs._stt_loop,  # pyright: ignore[reportPrivateUsage]
        args=(stop, done)
    )
    thread.start()

    # Allow the keyword loop to start waiting and trigger skip until speech
    for _ in range(5):
        time.sleep(0.05)
        if cb.texts:
            break
        fs.stt_skip_keyword_detection()

    # Wait for the first recognition to complete
    time.sleep(0.05)
    assert cb.texts == [mock_speechsdk.SpeechRecognizer.next_result_text]

    # Wait a bit longer to ensure a second iteration would run if keyword_done_event remained set
    time.sleep(0.1)
    assert cb.texts == [mock_speechsdk.SpeechRecognizer.next_result_text]

    stop.set()
    done.set()
    thread.join(timeout=1)


@pytest.mark.skipif(sys.platform != "linux", reason="Requires fork-based multiprocessing and ALSA")
def test_process_lifecycle_with_real_processes(mock_speechsdk: SimpleNamespace):
    _ = mock_speechsdk
    fs, _ = make_speech()

    fs.start()
    time.sleep(0.1)
    assert fs._tts_proc.is_alive()  # pyright: ignore[reportPrivateUsage]
    assert fs._stt_proc.is_alive()  # pyright: ignore[reportPrivateUsage]

    fs.stop()
    assert fs._stt_stop_event.is_set()  # pyright: ignore[reportPrivateUsage]
    assert fs._tts_stop_event.is_set()  # pyright: ignore[reportPrivateUsage]

    fs.join()
    assert not fs._tts_proc.is_alive()  # pyright: ignore[reportPrivateUsage]
    assert not fs._stt_proc.is_alive()  # pyright: ignore[reportPrivateUsage]
