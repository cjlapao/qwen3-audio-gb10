# qwen3-tts

OpenAI-compatible text-to-speech API powered by [Qwen3-TTS](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base).

## Overview

This service provides a FastAPI server for the **Faster Qwen3 TTS** model with three voice generation modes:

| Mode | How it works | Model |
|---|---|---|
| **Clone** | Zero-shot voice cloning from a ~10 s reference audio clip | [Qwen/Qwen3-TTS-12Hz-0.6B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base) |
| **Custom** | Use a preset speaker identity (e.g. "announcer", "whisper") | [Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice) |
| **Design** | Generate a voice from a text description (e.g. *"warm British narrator"*) | [Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign) |

**Primary model:** [Qwen/Qwen3-TTS-12Hz-0.6B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base)

## Voice System

Voices are stored on disk as directories under `/app/voices`. Each voice directory contains:

| File | Purpose |
|---|---|
| `voice.yaml` | Voice metadata (name, mode, parameters, language, etc.) |
| `ref_audio.wav` | Reference audio clip (clone mode only) |
| `speaker.pt` | Cached speaker embedding (clone mode, auto-generated) |

### Creating a voice

1. **Clone mode** — Upload a ~10 s clean audio clip (no music, minimal noise) along with its transcript. The system extracts a speaker embedding and caches it as `speaker.pt` for fast subsequent generations.
2. **Design mode** — Provide a text instruction describing the voice (e.g. *"cheerful young girl, slight accent"*). Each generation will vary slightly; for a stable persona, generate once, capture a sample, then clone from that sample.
3. **Custom mode** — Use a built-in preset speaker ID.

Voices persist across restarts when the `./voices` directory is volume-mounted.

## API Endpoints

### OpenAI-Compatible

#### `POST /v1/audio/speech`

Generate speech for given text.

```bash
curl -X POST http://localhost:8005/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "tts-1",
    "input": "Hello world!",
    "voice": "default"
  }' \
  --output speech.wav
```

| Field | Type | Required | Description |
|---|---|---|---|
| `model` | `string` | Yes | Always `"tts-1"` (reserved) |
| `input` | `string` | Yes | Text to synthesize |
| `voice` | `string` | Yes | Voice name (must exist) |
| `response_format` | `string` | No | `"wav"` (default) or `"mp3"` |

#### `GET /v1/audio/voices`

List available voice names.

```bash
curl http://localhost:8005/v1/audio/voices
# {"voices": ["default", "jarvis", "clone1"]}
```

#### `GET /v1/models`

Return model info.

```bash
curl http://localhost:8005/v1/models
# {"data": [{"id": "tts-1", "object": "model"}]}
```

### Rich API (Playground)

#### `POST /tts/generate`

Generate speech with per-request parameter overrides.

```bash
curl -X POST http://localhost:8005/tts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "voice": "default",
    "text": "Hello world!",
    "temperature": 0.8,
    "top_p": 0.9,
    "instruct": "in a warm whisper",
    "language": "en"
  }' \
  --output speech.wav
```

| Field | Type | Default | Description |
|---|---|---|---|
| `voice` | `string` | *(required)* | Voice name |
| `text` | `string` | *(required)* | Text to synthesize |
| `temperature` | `float` | voice default | Sampling temperature |
| `top_p` | `float` | voice default | Nucleus sampling threshold |
| `instruct` | `string` | voice default | Voice instruction override |
| `language` | `string` | voice default | Language code |

#### `GET /tts/voices`

List all voices with metadata.

```bash
curl http://localhost:8005/tts/voices
# [{"name": "default", "mode": "clone", "description": "...", "language": "English"}]
```

#### `GET /tts/voices/{name}`

Get a single voice's full configuration.

#### `POST /tts/voices/{name}/save`

Save/update voice metadata (temperature, top_p, instruct, etc.).

#### `POST /tts/voices/{name}/upload_audio`

Create or replace a clone voice with a new reference audio clip.

| Field | Type | Default | Description |
|---|---|---|---|
| `file` | `multipart` | *(required)* | Audio file (WAV, ~10 s) |
| `ref_text` | `form` | `""` | Transcript of the reference audio |
| `xvec_only` | `form` | `true` | Use x-vector only mode (faster, cleaner language switching) |
| `description` | `form` | `""` | Voice description |

#### `POST /tts/reload`

Reload voices from disk (useful after manually adding/removing voice directories).

```bash
curl -X POST http://localhost:8005/tts/reload
# {"voices": ["default", "jarvis"]}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MODEL_BASE` | `Qwen/Qwen3-TTS-12Hz-0.6B-Base` | Base model for voice cloning |
| `MODEL_CUSTOM` | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | Model for preset speakers |
| `MODEL_DESIGN` | `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | Model for text-described voices |
| `HF_HOME` | `/models` | Hugging Face model cache directory |
| `HF_HUB_ENABLE_HF_TRANSFER` | `1` | Enable fast HF downloads |
| `CUDA_VISIBLE_DEVICES` | `0` | GPU device assignment |
| `VOICES_ROOT` | `/app/voices` | Directory for voice storage |
| `TTS_HOST_PORT` | `8005` | Host port for TTS API |
| `TTS_UI_HOST_PORT` | `8006` | Host port for TTS UI |

## Requirements

- NVIDIA GPU (CUDA)
- 8 GB+ VRAM (bfloat16)

## Quick Start

### Docker Compose (production — from ghcr.io)

Runs TTS API + Gradio UI + optional Playground:

```bash
docker compose --file docker-compose.prod.yml up -d
```

### Docker Compose (development — build from source)

```bash
docker compose --file docker-compose.dev.yml up -d
```

### Access points

| Service | URL |
|---|---|
| TTS API (OpenAI-compatible) | `http://localhost:8005` |
| TTS Gradio UI | `http://localhost:8006` |
| Voice Playground (optional) | `http://localhost:8007` |

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Voice Library  │────▶│  qwen3-tts API   │────▶│  HuggingFace Hub │
│  (Gradio /      │     │  (FastAPI)       │     │  (model download)│
│   Playground)   │     │                  │     │                  │
└─────────────────┘     │  /v1/audio/      │     └──────────────────┘
                        │  /tts/           │
                        └──────────────────┘
                                │
                        ┌───────▼────────┐
                        │  /app/voices/  │
                        │  (persistent)  │
                        └────────────────┘
```
