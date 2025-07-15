# `fifo_dev_perception.speech.fifo_speech.FifoSpeech`

**FifoSpeech** is a Python module for managing speech input and output using **Azure Cognitive Services**. It supports:

- **Wake word detection** (offline, using a `.table` model)
- **Cloud-based speech-to-text (STT)**
- **Cloud-based text-to-speech (TTS)** with queue management and interruption support

**FifoSpeech** is designed for **Linux** and currently supports **ALSA audio devices only**.  
It extracts `plughw:X,Y` device names from the output of `sounddevice.query_devices()` and uses them for audio I/O.

The following two tasks run in separate background processes, providing improved robustness and parallel execution:

- **Wake word detection and speech-to-text (STT)**
- **Text-to-speech (TTS) playback**

---

## 🎯 Project Status & Audience

🚧 **Work in Progress** — Part of the **`fifo-dev-perception`** project, currently in **early development**. 🚧

This is a personal project developed and maintained by a solo developer.  
Contributions, ideas, and feedback are welcome, but development is driven by personal time and priorities.

Designed for **individual developers and robotics enthusiasts** experimenting with **speech and vision capabilities in hobby projects**.

No official release or pre-release has been published yet. The code is provided for **preview and experimentation**.  
**Use at your own risk.**

---

## 🛠️ Requirements

- Python 3.10+
- **Azure Cognitive Services (Speech)** (API key is required to create a FifoSpeech instance)
- Azure Speech **Custom Keyword model** (`.table` file)
- Linux with **ALSA** support
- **PortAudio** (required by `sounddevice`)

### 🖥️ System Dependencies

```bash
sudo apt install libportaudio2
```

---

## 📦 Installation

```bash
git clone https://github.com/gh9869827/fifo-dev-perception.git

cd fifo-dev-perception

python3 -m pip install -e .
```

---

## 🚀 Usage Example

### 📝 Create your Python script

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
    microphone="C922",          # Substring of input device name
    speaker="USB Audio",        # Substring of output device name
    voice_name="en-US-AvaMultilingualNeural",
    azure_key_env_var="AZURE_SPEECH_KEY",
    azure_region="westus2"
)

speech.start()
speech.text_to_speech("Hello! I'm ready. How can I help?", immediate=True)

# Run your main loop here...

speech.stop()
speech.join()
```

---

### 🔐 Set your Azure API key

Export your Azure Speech key before running the script:

```bash
# Add a space before the command to prevent it from being saved in your bash shell history
# (this behavior requires the HISTCONTROL environment variable to be set to 'ignorespace' or
# 'ignoreboth', which is usually the default)
# AZURE_SPEECH_KEY is referenced via the `azure_key_env_var` argument in FifoSpeech
 export AZURE_SPEECH_KEY="your-azure-speech-api-key"

python your_script.py
```

---

## ✅ License

MIT — see [LICENSE](../../LICENSE)

---

## 📄 Third-Party Disclaimer & Attribution

This project is not affiliated with or endorsed by Microsoft or the Azure Speech Services team.  
It builds on publicly documented [Azure Cognitive Services Speech SDKs](https://learn.microsoft.com/azure/cognitive-services/speech-service/) and APIs under their respective licenses.

This includes support for keyword spotting models (`.table` files), cloud-based speech-to-text, and text-to-speech.  
It uses the Azure Cognitive Services Speech SDK following **standard usage patterns** described in Azure documentation and examples. See [Microsoft's official Speech SDK examples](https://github.com/Azure-Samples/cognitive-services-speech-sdk) for reference; these examples are available under the MIT license.
