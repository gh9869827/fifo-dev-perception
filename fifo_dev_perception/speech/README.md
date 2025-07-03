# FifoSpeech

FifoSpeech is a Python module for managing speech input and output using Azure Cognitive Services. It supports:

- Wake word detection (offline, using a `.table` model)
- Cloud-based speech-to-text (STT)
- Cloud-based text-to-speech (TTS), with queue management and interruption support

It is designed to run on **Linux**, using **ALSA** device names. It provides process isolation for robustness and parallelism using two background processes:
  - Wake word + STT
  - TTS playback

---

## 🛠️ Requirements

- Python 3.10+
- Azure Cognitive Services subscription (Speech)
- Azure Speech Custom Keyword model (`.table`)
- Linux (ALSA-based audio support only)
- PortAudio (required by `sounddevice`)

### 🖥️ System Dependencies

```bash
sudo apt install libportaudio2
```

### 📦 Python Package

```bash
git clone https://github.com/gh9869827/fifo-dev-perception.git

cd fifo-dev-perception

python3 -m pip install -e .
```

---

## 🚀 Usage

```python
from fifo_speech import FifoSpeech, FifoSpeechCallback

class MyCallback(FifoSpeechCallback):
    def on_stt_keyword_recognized(self, keyword: str, speech: FifoSpeech):
        print("Wake word detected:", keyword)

    def on_stt_text_recognized(self, text: str, speech: FifoSpeech):
        print("Recognized text:", text)

    def on_tts_synthesis_done(self, request_id: str, success: bool):
        print("TTS done", request_id, success)

speech = FifoSpeech(
    wake_word_model="keyword.table",
    callback=MyCallback(),
    microphone="C922",          # Substring of input device
    speaker="USB Audio",        # Substring of output device
    voice_name="en-US-AvaMultilingualNeural",
    azure_key_env_var="AZURE_SPEECH_KEY",
    azure_region="westus2"
)

speech.start()
speech.text_to_speech("Hello! I'm ready. How can I help?", immediate=True)

...

speech.stop()
speech.join()
```

---

## ✅ License

MIT — see [LICENSE](../../LICENSE) for details.

---

## 📄 Disclaimer

This project is not affiliated with or endorsed by Microsoft or the Azure Speech Services team.  
It builds on their publicly documented APIs and SDKs under their respective licenses.

---

## 📄 Attribution

This project uses the [Azure Cognitive Services Speech SDK](https://learn.microsoft.com/azure/cognitive-services/speech-service/),
including support for keyword spotting models (`.table` files) and cloud-based speech-to-text and text-to-speech.

Any code structure or logic adapted from Azure documentation is used under the terms of the MIT or standard documentation license.  
See [Microsoft's official Speech SDK examples](https://github.com/Azure-Samples/cognitive-services-speech-sdk) for reference implementations.
