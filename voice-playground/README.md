# voice-playground

A Gradio-based voice library and testing UI for [qwen3-tts](../qwen3-tts/).

## Overview

Voice Playground is a web interface that lets you:

- **Test & tune** existing voices — select a voice, type text, adjust temperature/top-p/instruction, and listen to the result.
- **Create clone voices** — upload a ~10 s reference audio clip (from file or microphone) with its transcript to create a new voice.
- **Create design voices** — describe a voice in text (e.g. *"warm British narrator, mid-tempo, slight gravel"*) and generate a design-mode voice from it.

It connects to a running qwen3-tts API instance via HTTP.

## Tabs

### Test & Tune

Pick a voice from the dropdown, enter text, and hit Generate. Adjust:

- **Temperature** (`0.0` – `1.5`) — Higher = more varied/expressive, lower = more consistent.
- **Top-p** (`0.1` – `1.0`) — Nucleus sampling threshold.
- **Instruction** — Optional text override (e.g. *"in a low conspiratorial whisper"*).

Click **Save as defaults** to persist your preferred parameters for that voice.

### Create from Audio (Clone)

1. Enter a **voice name** (this becomes the folder name on the TTS server).
2. Add a **description**.
3. Upload a **reference audio clip** (~10 seconds, clean speech, no music).
4. Optionally provide a **reference transcript** — leave empty for x-vector mode (faster, cleaner language switching).
5. Click **Create voice**.

### Create from Description (Design)

1. Enter a **voice name** and **description**.
2. Provide a **voice instruction** — a detailed text description of the desired voice character.
3. Set the **language** and generation parameters.
4. Click **Create design voice**.

> **Tip:** Design-mode voices vary slightly between generations. For a stable persona, generate once, capture a sample audio, then use the **Clone** tab to lock in that voice.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TTS_BASE` | `http://qwen3-tts:8000` | URL of the qwen3-tts API |
| `PLAYGROUND_HOST_PORT` | `8006` | Host port mapping (docker-compose only) |

## Requirements

- CPU-friendly — no GPU required for this service
- Python 3.12+

## Quick Start

### Docker Compose (production — from ghcr.io)

```bash
docker compose --file docker-compose.prod.yml up -d
```

### Docker Compose (development — build from source)

```bash
docker compose --file docker-compose.dev.yml up -d
```

### Run standalone (no Docker)

```bash
pip install gradio>=5.0 requests soundfile numpy
python app.py
```

## Architecture

```
┌──────────────────┐     HTTP     ┌──────────────────┐
│  Voice Playground │────────────▶│  qwen3-tts API   │
│  (Gradio, port 7860)  requests  │  (FastAPI, port  │
└──────────────────┘              │   8000)          │
                                  │                  │
                                  │  /tts/generate   │
                                  │  /tts/voices     │
                                  └──────────────────┘
```
