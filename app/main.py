"""
Unified entrypoint. Reads SERVICE_MODE and exposes the matching FastAPI app
as `app`. uvicorn imports this module and serves whichever app got built.
"""
import os
import sys

mode = os.getenv("SERVICE_MODE", "").lower().strip()

if mode == "tts":
    print(f"[main] starting in TTS mode", flush=True)
    from tts_server import app
elif mode == "asr":
    print(f"[main] starting in ASR mode", flush=True)
    from asr_server import app
else:
    print(f"[main] SERVICE_MODE must be 'tts' or 'asr', got '{mode}'",
          file=sys.stderr, flush=True)
    sys.exit(1)