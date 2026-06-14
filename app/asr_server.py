# asr_server.py
import os
import tempfile
import torch
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from qwen_asr import Qwen3ASRModel

MODEL_BASE = os.getenv("MODEL_BASE", "Qwen/Qwen3-ASR-1.7B")

print(f"[asr] booting; model {MODEL_BASE}", flush=True)
_models: dict[str, Qwen3ASRModel] = {}


def get_model(kind: str = "asr") -> Qwen3ASRModel:
    if kind not in _models:
        print(f"[asr] loading {MODEL_BASE}...", flush=True)
        _models[kind] = Qwen3ASRModel.from_pretrained(
            MODEL_BASE,
            dtype=torch.bfloat16,
            device_map="cuda:0",
            max_inference_batch_size=8,
            max_new_tokens=512,
        )
        print(f"[asr] model loaded", flush=True)
    return _models[kind]


# Eager-load at boot so first request isn't slow.
# (TTS lazy-loads because it has three variants; ASR has just one, no benefit.)
get_model()

app = FastAPI()


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(None),                 # OpenAI form field; no shadow now
    language: str = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0.0),
):
    suffix = os.path.splitext(file.filename or "")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        results = get_model().transcribe(
            audio=tmp_path,
            language=language,               # None = auto-detect
        )
        text = results[0].text
        lang = results[0].language

        if response_format in ("text", "txt"):
            return text
        return JSONResponse({"text": text, "language": lang})
    finally:
        os.unlink(tmp_path)


@app.get("/v1/models")
def models():
    return {"data": [{"id": MODEL_BASE, "object": "model"}]}