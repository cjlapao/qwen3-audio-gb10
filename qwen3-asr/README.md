# qwen3-asr

OpenAI-compatible speech-to-text API powered by [Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B).

## Overview

This service wraps the Qwen3-ASR model behind a FastAPI server that accepts audio files and returns transcribed text, with auto language detection. It implements the same `/v1/audio/transcriptions` endpoint shape as OpenAI's API so you can swap in any compatible client.

**Model:** [Qwen/Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)

## API Endpoints

### `POST /v1/audio/transcriptions`

Transcribe audio to text.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file` | `multipart/form-data` | *(required)* | Audio file (any format supported by torchaudio) |
| `model` | `form` | None | Override model (currently unused, reserved for multi-model support) |
| `language` | `form` | None | Language code (e.g. `"en"`, `"zh"`). Leave empty for auto-detect. |
| `response_format` | `form` | `"json"` | `"json"`, `"text"`, or `"txt"` |
| `temperature` | `form` | `0.0` | Sampling temperature (fixed at 0 for transcription) |

**Example:**

```bash
curl -X POST http://localhost:8004/v1/audio/transcriptions \
  -F "file=@recording.wav" \
  -F "response_format=json"
```

**Response (JSON):**
```json
{
  "text": "The future belongs to those who automate the boring bits.",
  "language": "en"
}
```

### `GET /v1/models`

Return the loaded model info.

```bash
curl http://localhost:8004/v1/models
# {"data": [{"id": "Qwen/Qwen3-ASR-1.7B", "object": "model"}]}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MODEL_ID` | `Qwen/Qwen3-ASR-1.7B` | Hugging Face model ID |
| `HF_HOME` | `/models` | Directory for cached Hugging Face models |
| `ASR_HOST_PORT` | `8004` | Host port mapping (docker-compose only) |

## Requirements

- NVIDIA GPU (CUDA)
- 8 GB+ VRAM (bfloat16)

## Quick Start

### Build & run (local)

```bash
make build-asr
make push-asr
```

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
pip install qwen-asr fastapi uvicorn[standard] torch torchaudio
uvicorn asr_server:app --host 0.0.0.0 --port 8004
```
