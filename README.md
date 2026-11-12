# NOVA — Neural Optimised Voice-activated Assistant

![Python](https://shields.io)
![License](https://shields.io)
![Platform](https://shields.io)

**NOVA** is a modular, voice-activated desktop assistant built in Python. Originally developed as an OCR GCE A-Level Computer Science coursework project (`H446-03`), NOVA was designed to make everyday computer interactions faster, more intuitive, and accessible—particularly for students, multitaskers, and users with physical impairments who benefit from hands-free control.

---

## Table of Contents
- [Features](#-features)
- [System Architecture](#-system-architecture)
- [Prerequisites & Installation](#-prerequisites--installation)
- [Usage & Example Commands](#-usage--example-commands)
- [Security & Safety Nets](#-security--safety-nets)
- [Testing & Evaluation Benchmarks](#-testing--evaluation-benchmarks)
- [Known Limitations](#-known-limitations)
- [Aspirational Roadmap (Future Development)](#-aspirational-roadmap-future-development)

---

## Features

* **Wake-Word Activation:** Passively listens in lightweight intervals for `"Hey NOVA"` or `"NOVA"` before engaging active command processing.
* **Natural Language Processing (NLP):** Uses regex parsing, tokenization, and a custom synonym-mapping lexicon (`synonymsMap`) so you don't have to memorize rigid commands.
* **Smart File Management:** Recursively searches your home directory to locate and open files using just a filename, relative path, or quoted string.
* **Web & Media Automation:** Launches Google searches in your default browser and plays local media files—automatically falling back to a YouTube search if a track isn't found locally.
* **Contextual Memory:** Remembers your most recently accessed file, search query, and song to support quick follow-up commands.
* **Multimodal Accessibility Feedback:** Combines offline Text-to-Speech (`pyttsx3`) with real-time terminal state indicators (`[◉ Listening]`, `[… Processing]`, `[✓ Success]`, `[✗ Error]`) and graceful text fallbacks if audio hardware fails.
* **Dual-Layer Structured Logging:** Records every boot event, command, warning, and exception with timestamps to both an in-memory list (`systemLog`) and a persistent JSON-formatted `nova.log` file.

---

## System Architecture

NOVA is structured around a decoupled, single-responsibility pipeline so individual modules can be upgraded or replaced independently:

1. **Audio Input & STT Layer (`listenOnce`, `transcribeAudio`):** Captures microphone streams via `PyAudio`, calibrates for ambient noise, and transcribes speech via Google's Speech Recognition API.
2. **Wake Word Layer (`detectWakePhrase`):** Filters out background chatter until the trigger phrase is detected.
3. **Command Processor Layer (`tokenize`, `matchIntent`, `extractParameters`):** Normalises spoken input, maps synonyms, classifies user intent against `intentDb`, and extracts target parameters.
4. **Security & Validation Layer (`checkPermission`, `safeOpenPath`, `confirmActionViaVoice`):** Enforces capability permissions and directory sandboxing before execution.
5. **Task Execution Layer (`executeTask`):** A central dispatcher dictionary (`taskMap`) that routes validated intents to handlers (`openFile`, `searchWeb`, `playMusic`).
6. **Feedback & Diagnostics Layer (`provideFeedback`, `logEvent`):** Delivers simultaneous audio/visual status updates and writes audit trails.

---

## Prerequisites & Installation

### 1. System Dependencies
NOVA relies on `PyAudio` for microphone input. Depending on your OS, you may need PortAudio installed first:
* **macOS:** `brew install portaudio`
* **Linux (Debian/Ubuntu):** `sudo apt-get install python3-pyaudio portaudio19-dev`
* **Windows:** Usually installs directly via `pip`.

### 2. Python Libraries
Clone the repository and install the required third-party packages:

```bash
git clone https://github.com
cd NOVA
pip install SpeechRecognition pyttsx3 pyaudio
```

*(Note: All other dependencies—`os`, `sys`, `re`, `time`, `json`, `webbrowser`, `subprocess`, `datetime`—are part of the Python Standard Library.)*

### 3. Configuration
Before running, you can tweak sensitivity and timeouts at the top of `NOVA.py` to match your microphone and environment:
```python
sampleRate = 16000          # Recommended standard audio frequency (Hz)
phraseTimeLimitWake = 2     # Seconds to listen for wake word
phraseTimeLimitCmd = 6      # Seconds to listen for full command
language = "en-GB"          # STT transcription locale
```
*(Note: Depending on your microphone hardware, you may also want to adjust `recognizer.energy_threshold` inside `listenOnce()`.)*

---

## Usage & Example Commands

Run the assistant from your terminal:
```bash
python NOVA.py
```

Once NOVA announces *"NOVA is online"*, say **"Hey NOVA"** or **"NOVA"**, wait for the *"Yes?"* prompt, and speak a command:

| Intent | Example Phrases | What NOVA Does |
| :--- | :--- | :--- |
| **`open_file`** | *"Open file report.docx"*, *"Launch notes.txt"*, *"Open it"* | Searches your home directory for the file and opens it in its default app (or reopens the last file in context). |
| **`search_web`** | *"Search web for Python threading"*, *"Google A-Level CS"*, *"Look up weather"* | Opens a Google search tab in your default web browser. |
| **`play_music`** | *"Play Believer"*, *"Play song chill beats"*, *"Start music"* | Plays a matching local audio file from your home directory, or searches YouTube if not found locally. |

Press `Ctrl + C` in the terminal to trigger a graceful shutdown.

---

## Security & Safety Nets

Because voice assistants interact directly with the host operating system, NOVA includes built-in safeguards:
* **Directory Sandboxing:** `checkPermission()` resolves absolute paths and blocks file operations outside the user's home directory (`~`) to prevent directory traversal attacks.
* **Capability Matrix:** Every intent is checked against a `permissions` dictionary (`read`, `write`, `delete`, `net`, `media`) prior to execution.
* **Verbal Confirmation Prompts:** High-risk or destructive intents (such as `delete_file` or `overwrite_file`) trigger `confirmActionViaVoice()`, requiring an explicit spoken *"Yes"* within 4 seconds before proceeding.

---

## Testing & Evaluation Benchmarks

During post-development evaluation against defined engineering criteria, NOVA achieved the following results:

* **Execution Speed:** `1.2s – 1.8s` average turnaround from speech recognition to task execution (Target: `≤ 2.0s`).
* **Voice Recognition Accuracy:** `88%` across 50 controlled test cases (44/50 commands recognized accurately in varied environments).
* **Error Recovery:** `92.8%` recovery rate (13/14 simulated failure cases handled via spoken/visual alerts and logs without crashing).
* **Cross-Platform Compatibility:** Verified functional across Windows 10, Windows 11, and macOS.

---

## Known Limitations

* **Internet Dependency for STT:** While TTS is completely offline, speech-to-text currently relies on Google's free web API, requiring an active internet connection.
* **Static Energy Thresholds:** Background noise calibration relies on manual threshold tuning rather than a dedicated neural voice-activity detector.
* **CLI-Only Interface:** Interaction currently takes place via terminal output and audio rather than a graphical interface.
* **Rule-Based NLP:** Intent matching uses keyword/synonym dictionaries and regex rather than machine learning classifiers.

---

## Aspirational Roadmap (Future Development)

Now that the core coursework prototype is complete, future updates to NOVA aim to explore:

- [ ] **100% Offline Speech Pipeline:** Replace cloud STT with local models like **OpenAI Whisper** or **Vosk** for full offline privacy and lower latency.
- [ ] **Dedicated Neural Wake-Word Engine:** Integrate **Picovoice Porcupine** or **Mycroft Precise** with noise suppression/VAD to improve wake-word accuracy in noisy rooms.
- [ ] **External Configuration & Custom Commands:** Move `intentDb`, `synonymsMap`, and microphone thresholds into an external `config.json` / `YAML` file so non-technical users can add custom routines without editing source code.
- [ ] **Desktop GUI & Visual Previews:** Build a lightweight front-end (using `PyQt`, `Tkinter`, or `Electron`) featuring pulsing audio visualizers, live transcription captions, and on-screen file previews.
- [ ] **Advanced ML Intent Classification:** Upgrade regex/dictionary parsing to **spaCy** (`textcat`) or lightweight transformer models for richer conversational context and Named Entity Recognition (NER).
- [ ] **Multi-Threaded Concurrency & Productivity Suite:** Implement Python `threading` to support background timers, spoken reminders, voice-activated note-taking, and calendar integration.
