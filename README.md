# qwen3-audio-gb10

Run [Qwen3-ASR](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) and [Qwen3-TTS](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) on an NVIDIA GB10 (or any ARM64 Blackwell box) as OpenAI-compatible APIs from a single Docker image.

Both services share one codebase, one Dockerfile, and one image. A `SERVICE_MODE` environment variable decides whether a container boots in ASR or TTS mode. The voice playground stays as its own small image — different dependency profile, no GPU.

## What you get

| Service | Mode | Port | Endpoint shape |
|---|---|---|---|
| **qwen3-asr** | Speech-to-text | 8004 | OpenAI `/v1/audio/transcriptions` |
| **qwen3-tts** | Text-to-speech | 8005 | OpenAI `/v1/audio/speech` + rich `/tts/*` |
| **voice-playground** | Gradio UI | 8006 | Web UI for testing and tuning voices |

Both audio services speak OpenAI's API shape, so OpenWebUI, LiteLLM, and anything else that talks to Whisper or OpenAI TTS will just work.

## Quick start

```bash
# One-time: log in to ghcr.io if you're pulling prebuilt images
docker login ghcr.io -u cjlapao -p <personal-access-token>

# Build the unified image
make build

# Bring up ASR + TTS
docker compose up -d

# Add the playground UI too (opt-in)
docker compose --profile playground up -d

# Tail logs
make logs
```

ASR comes up on `http://localhost:8004`, TTS on `http://localhost:8005`, playground on `http://localhost:8006`.

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │   qwen3-audio-gb10 image            │
                    │   (one build, two runtime modes)    │
                    │                                     │
                    │   app/                              │
                    │     main.py        ← reads          │
                    │                      SERVICE_MODE   │
                    │     asr_server.py                   │
                    │     tts_server.py                   │
                    │     voice_store.py                  │
                    └──────────┬──────────────┬───────────┘
                               │              │
                       SERVICE_MODE=asr   SERVICE_MODE=tts
                               │              │
              ┌────────────────▼────┐   ┌─────▼─────────────────┐
              │  qwen3-asr          │   │  qwen3-tts            │
              │  :8004              │   │  :8005                │
              │                     │   │                       │
              │  /v1/audio/         │   │  /v1/audio/speech     │
              │   transcriptions    │   │  /v1/audio/voices     │
              │  /v1/models         │   │  /tts/generate        │
              │                     │   │  /tts/voices/*        │
              └─────────────────────┘   │  /tts/reload          │
                                        └───────────┬───────────┘
                                                    │
                                            ┌───────▼──────┐
                                            │  ./voices/   │
                                            │  YAML + WAVs │
                                            │  + cached    │
                                            │  embeddings  │
                                            └──────────────┘

                            ┌──────────────────────┐
                            │  voice-playground    │
                            │  (separate image)    │
                            │  :8006               │
                            │  Gradio UI calls     │
                            │  qwen3-tts over HTTP │
                            └──────────────────────┘
```

## Models

The image installs `faster-qwen3-tts` and `qwen-asr` from upstream. Model weights download from Hugging Face on first use and persist in the mounted `models/` volume.

| Model | Hugging Face |
|---|---|
| Qwen3-ASR-1.7B | [Qwen/Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) |
| Qwen3-TTS-12Hz-1.7B-Base (clone mode) | [Qwen/Qwen3-TTS-12Hz-1.7B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) |
| Qwen3-TTS-12Hz-1.7B-CustomVoice | [Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice) |
| Qwen3-TTS-12Hz-1.7B-VoiceDesign | [Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign) |

TTS lazy-loads each variant on first request, so memory only grows as you use modes. ASR eager-loads at boot.

## Voice library

TTS voices live in `voices/` on the host, mounted into the container. Each voice is a folder containing a `voice.yaml` recipe and (for clone-mode voices) a `ref_audio.wav` reference clip:

```
voices/
├── carlos/
│   ├── voice.yaml
│   ├── ref_audio.wav
│   └── speaker.pt          ← auto-generated cache
├── jarvis/
│   ├── voice.yaml
│   ├── ref_audio.wav
│   └── speaker.pt
└── narrator-warm/
    └── voice.yaml          ← design-mode, no audio
```

A clone voice's YAML:

```yaml
name: carlos
description: My narration voice
mode: clone
ref_audio: ref_audio.wav
ref_text: "Reference transcript here..."
xvec_only: true
language: English
temperature: 0.4
top_p: 0.85
```

A design voice's YAML — no reference audio, just an instruction prompt:

```yaml
name: jarvis
mode: design
description: Calm British AI butler
instruct: "Calm, measured, articulate British male voice with a hint of dry wit"
language: English
temperature: 0.6
top_p: 0.85
```

Add a voice by either creating the folder directly and calling `POST /tts/reload`, or use the playground's "Create from Audio" tab.

## Build & publish

```bash
make build         # build the unified image locally
make push          # tag :latest and push :<version> and :latest to ghcr.io
make build-play    # build the playground image
make push-play     # push the playground image

# Override defaults
make VERSION=v1.0.0 build push
make PUSH_REPO=ghcr.io/myuser/private build
```

See `make help` for the full target list.

## Run modes

### Default (build from source, both services)

```bash
docker compose up -d                          # ASR + TTS
docker compose --profile playground up -d     # + playground UI
```

### Production (consume prebuilt images from ghcr.io)

```bash
docker compose --file docker-compose.prod.yml up -d
```

### Single service

```bash
docker compose up -d qwen3-asr               # ASR only
docker compose up -d qwen3-tts               # TTS only
docker compose --profile playground up -d voice-playground   # playground only
```

## Environment overrides

Everything's parameterized via env vars. Drop a `.env` next to the compose file or pass them inline.

| Variable | Default | Used by |
|---|---|---|
| `ASR_HOST_PORT` | `8004` | Compose port mapping for ASR |
| `ASR_MODEL_BASE` | `Qwen/Qwen3-ASR-1.7B` | ASR model identifier |
| `TTS_HOST_PORT` | `8005` | Compose port mapping for TTS |
| `TTS_MODEL_BASE` | `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | Clone-mode model |
| `TTS_MODEL_CUSTOM` | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | Custom-voice model |
| `TTS_MODEL_DESIGN` | `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | Design-mode model |
| `PLAYGROUND_HOST_PORT` | `8006` | Compose port mapping for playground |
| `IMAGE_PREFIX` | `ghcr.io/cjlapao` | Registry/owner for prod compose |
| `IMAGE_TAG` | `latest` | Image tag for prod compose |

Examples:

```bash
# Move ASR to a different port and use a smaller model
ASR_HOST_PORT=9004 ASR_MODEL_BASE=Qwen/Qwen3-ASR-0.6B docker compose up -d

# Pull a specific build from a fork
IMAGE_PREFIX=ghcr.io/myuser IMAGE_TAG=v1.2.0 \
  docker compose --file docker-compose.prod.yml --profile playground up -d
```

## OpenWebUI integration

In OpenWebUI's Settings → Audio:

**STT (Speech-to-Text):**
- Engine: OpenAI
- API Base URL: `http://<gb10-ip>:8004/v1`
- API Key: anything non-empty
- Model: `Qwen/Qwen3-ASR-1.7B`

**TTS:**
- Engine: OpenAI
- API Base URL: `http://<gb10-ip>:8005/v1`
- API Key: anything non-empty
- TTS Model: `tts-1`
- TTS Voice: whatever folder name exists in `voices/` (e.g. `default`, `carlos`, `jarvis`)
- TTS Split On: `paragraph` (recommended — see [Tuning tips](#tuning-tips))

## Tuning tips

A few things worth knowing once you're past initial setup:

**Voices drift between sentences.** OpenWebUI chunks text and calls TTS per chunk. To keep a voice consistent across chunks, lower the temperature on that voice (`0.4` instead of `0.7`) and keep `xvec_only: true`. The included `add_natural_tail` post-processor smooths the audio joins so transitions sound continuous.

**Stable AI personas.** Voice Design mode generates a fresh voice each call, so the same `jarvis` design will sound slightly different each time. To freeze a persona: design once, capture a sample you like, then promote it to a clone voice using that sample as the reference. The end result is a stable, reproducible voice.

**First request is slow.** TTS lazy-loads each model variant on first use (clone, custom, design). The first call to a mode takes 30-60s for model load + CUDA graph capture. Subsequent calls are fast. ASR eager-loads at boot, so it's slow at container start but consistent thereafter.

**Voice library is the source of truth.** Drop a folder in `voices/`, edit any YAML, `curl -X POST http://localhost:8005/tts/reload`, and the new state is live. No restarts. Back up `voices/` to keep your library portable.

## Requirements

- NVIDIA GPU with CUDA 13 and SM_121 support (GB10 / Blackwell)
- ARM64 host (the NGC PyTorch base ships ARM64-native)
- Docker Compose v2
- `nvidia-container-toolkit`
- About 15GB free for model weights on first run

x86_64 users: the base image (`nvcr.io/nvidia/pytorch:25.10-py3`) has x86_64 variants too. Should work but isn't tested here.

## Project structure

```
qwen3-audio-gb10/
├── README.md                          ← this file
├── Makefile                           ← build/push/run helpers
├── docker-compose.yml                 ← dev: build from source
├── docker-compose.prod.yml            ← prod: pull from ghcr.io
├── Dockerfile                         ← unified image
├── app/
│   ├── main.py                        ← reads SERVICE_MODE, dispatches
│   ├── asr_server.py                  ← FastAPI ASR server
│   ├── tts_server.py                  ← FastAPI TTS server
│   └── voice_store.py                 ← voice library persistence
├── voices/                            ← persistent voice library
│   └── default/
│       ├── voice.yaml
│       └── ref_audio.wav
└── voice-playground/                  ← separate small image
    ├── Dockerfile
    ├── app.py
    ├── docker-compose.dev.yml
    ├── docker-compose.prod.yml
    └── README.md
```

## License

Built on top of upstream projects under their respective licenses:

- [faster-qwen3-tts](https://github.com/andimarafioti/faster-qwen3-tts) — Apache 2.0
- [qwen-asr](https://github.com/QwenLM/Qwen3-ASR) — Apache 2.0
- Qwen3 model weights — see each model card on Hugging Face