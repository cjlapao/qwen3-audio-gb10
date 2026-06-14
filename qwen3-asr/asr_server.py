# asr_server.py
import io
import os
import tempfile
import torch
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from qwen_asr import Qwen3ASRModel

MODEL_ID = os.getenv("MODEL_ID", "Qwen/Qwen3-ASR-1.7B")

app = FastAPI()
model = Qwen3ASRModel.from_pretrained(
    MODEL_ID,
    dtype=torch.bfloat16,
    device_map="cuda:0",
    max_inference_batch_size=8,
    max_new_tokens=512,
)

@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(None),
    language: str = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0.0),
):
    suffix = os.path.splitext(file.filename or "")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        results = globals()["model"].transcribe(
            audio=tmp_path,
            language=language,  # None = auto-detect
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
    return {"data": [{"id": MODEL_ID, "object": "model"}]}
