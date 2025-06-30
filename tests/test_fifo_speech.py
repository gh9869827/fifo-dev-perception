import pytest
import os
import queue
import threading
import time
import importlib


def load_module():
    import fifo_dev_perception.speech.fifo_speech as mod
    return importlib.reload(mod)


class DummyCallback(load_module().FifoSpeechCallback):
    def __init__(self):
        self.keywords = []
        self.texts = []

    def on_keyword(self, keyword, speech):
        self.keywords.append(keyword)

    def on_text(self, text, speech):
        self.texts.append(text)


def make_speech(tmp_key_env="AZ_KEY"):
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
    assert fs._get_azure_key() == "secret"


def test_get_azure_key_missing():
    fs, _ = make_speech("MISSING")
    if "MISSING" in os.environ:
        del os.environ["MISSING"]
    with pytest.raises(RuntimeError):
        fs._get_azure_key()


def test_text_to_speech_queue_immediate():
    fs, _ = make_speech()
    fs._tts_queue = queue.Queue()
    fs.text_to_speech("first", False)
    fs.text_to_speech("second", True)
    assert fs._tts_interrupt_event.is_set()
    assert list(fs._tts_queue.queue) == ["second"]


def test_stt_skip_keyword_detection_sets_event():
    fs, _ = make_speech()
    fs.stt_skip_keyword_detection()
    assert fs._stt_keyword_done_event.is_set()


def test_tts_loop_runs_and_speaks(mock_speechsdk):
    fs, _ = make_speech()
    fs._tts_queue = queue.Queue()
    fs._tts_queue.put("hello")
    fs._tts_queue.put(None)
    interrupt = threading.Event()
    stop = threading.Event()
    thread = threading.Thread(target=fs._tts_loop, args=(interrupt, stop))
    thread.start()
    time.sleep(0.05)
    stop.set()
    interrupt.set()
    thread.join(timeout=1)
    assert "hello" in mock_speechsdk.SpeechSynthesizer.spoken_texts


def test_stt_loop_detects_and_recognizes(mock_speechsdk):
    fs, cb = make_speech()
    stop = threading.Event()
    done = threading.Event()
    thread = threading.Thread(target=fs._stt_loop, args=(stop, done))
    thread.start()
    time.sleep(0.05)
    stop.set()
    done.set()
    thread.join(timeout=1)
    assert cb.keywords == ["keyword"]
    assert cb.texts == [mock_speechsdk.SpeechRecognizer.next_result_text]
