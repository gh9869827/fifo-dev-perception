[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Test Status](https://github.com/gh9869827/fifo-dev-perception/actions/workflows/test.yml/badge.svg)

# fifo-dev-perception

Perception modules shared across the `fifo-bot-*` and `fifo-dev-*` repositories.

This repository provides speech and vision components optimized for edge devices. Modules are designed to be lightweight, modular, and easy to integrate into robotics and automation stacks.

---

## 🧩 Modules

### 🔊 Speech

Speech recognition and text-to-speech using Azure Cognitive Services:

- Wake word detection (offline, using a `.table` model)
- Cloud-based speech-to-text and text-to-speech
- Process isolation for robustness and parallelism

See [`fifo_dev_perception/speech/README.md`](fifo_dev_perception/speech/README.md) for full usage and setup instructions.

---

### 👁 Vision

Coming soon.

---

## 📦 Installation

```bash
git clone https://github.com/gh9869827/fifo-dev-perception.git

cd fifo-dev-perception

python3 -m pip install -e .
```

---

## ✅ License

MIT — see [LICENSE](LICENSE)

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
