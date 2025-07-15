[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Test Status](https://github.com/gh9869827/fifo-dev-perception/actions/workflows/test.yml/badge.svg)

# fifo-dev-perception

Perception modules shared across the `fifo-bot-*` and `fifo-dev-*` repositories.

This repository provides speech and vision components optimized for edge devices, such as the **Raspberry Pi**. Modules are designed to be lightweight, modular, and easy to integrate into robotics and automation stacks.

---

## 🎯 Project Status & Audience

🚧 **Work in Progress** — This project is in **early development**. 🚧

This is a personal project developed and maintained by a solo developer.  
Contributions, ideas, and feedback are welcome, but development is driven by personal time and priorities.

Designed for **individual developers and robotics enthusiasts** experimenting with **speech and vision capabilities in hobby projects**.

No official release or pre-release has been published yet. The code is provided for **preview and experimentation**.  
**Use at your own risk.**

---

## 🧩 Modules

### 🔊 Speech

Speech recognition and text-to-speech using Azure Cognitive Services:

- Wake word detection (offline, using a `.table` model)
- Cloud-based speech-to-text and text-to-speech
- Runs **wake word detection + speech-to-text** and **text-to-speech** in **separate background processes**, providing improved robustness and parallel execution.

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

## 📄 Third-Party Disclaimer & Attribution

This project is not affiliated with or endorsed by Microsoft or the Azure Speech Services team.  
It builds on publicly documented [Azure Cognitive Services Speech SDKs](https://learn.microsoft.com/azure/cognitive-services/speech-service/) and APIs under their respective licenses.

This includes support for keyword spotting models (`.table` files), cloud-based speech-to-text, and text-to-speech.  
It uses the Azure Cognitive Services Speech SDK following **standard usage patterns** described in Azure documentation and examples. See [Microsoft's official Speech SDK examples](https://github.com/Azure-Samples/cognitive-services-speech-sdk) for reference; these examples are available under the MIT license.
