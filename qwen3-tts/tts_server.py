# tts_server.py
import io
import wave
import numpy as np
import torch
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

from faster_qwen3_tts import FasterQwen3TTS
from voice_store import VoiceStore, Voice

import os
MODEL_BASE   = os.getenv("MODEL_BASE",   "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
MODEL_CUSTOM = os.getenv("MODEL_CUSTOM", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
MODEL_DESIGN = os.getenv("MODEL_DESIGN", "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign")

store = VoiceStore()
_models: dict[str, FasterQwen3TTS] = {}

def get_model(kind):
    if kind not in _models:
        ids = {"clone": MODEL_BASE, "custom": MODEL_CUSTOM, "design": MODEL_DESIGN}
        _models[kind] = FasterQwen3TTS.from_pretrained(ids[kind])
    return _models[kind]

def to_wav(audio, sr):
    if isinstance(audio, list):
        audio = np.concatenate([a.cpu().numpy() if hasattr(a, "cpu") else np.asarray(a) for a in audio])
    elif hasattr(audio, "cpu"):
        audio = audio.cpu().numpy()
    audio = np.asarray(audio).squeeze()
    audio = add_natural_tail(audio, sr, tail_ms=250)
    pcm = np.clip(audio * 32768, -32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()

def synthesize(voice: Voice, text: str, overrides: dict | None = None) -> bytes:
    """Generate audio from a Voice using its stored recipe, with optional overrides."""
    o = overrides or {}
    temperature = o.get("temperature", voice.temperature)
    top_p = o.get("top_p", voice.top_p)
    instruct = o.get("instruct", voice.instruct)
    language = o.get("language", voice.language)

    if voice.mode == "clone":
        model = get_model("clone")
        spk_emb = None
        if voice.speaker_pt:
            try:
                spk_emb = torch.load(voice.speaker_pt, weights_only=True).to(model.device)
                # Sanity check: the codec expects 1024-dim embeddings.
                # If we cached something larger (mode change leftover), bin it.
                if spk_emb.numel() != 1024 and spk_emb.shape[-1] != 1024:
                    print(f"stale embedding for '{voice.name}' "
                          f"(shape {tuple(spk_emb.shape)}), regenerating", flush=True)
                    os.unlink(voice.speaker_pt)
                    spk_emb = None
            except Exception as e:
                print(f"failed to load cached embedding for '{voice.name}': {e}", flush=True)
                spk_emb = None

        if spk_emb is not None:
            voice_clone_prompt = {"ref_spk_embedding": [spk_emb]}
        else:
            prompt_items = model.model.create_voice_clone_prompt(
                ref_audio=voice.ref_audio,
                ref_text=voice.ref_text,
                x_vector_only_mode=voice.xvec_only,
            )
            store.cache_embedding(voice.name, prompt_items[0].ref_spk_embedding)
            voice_clone_prompt = prompt_items

        audio, sr = model.generate_voice_clone(
            text=text, language=language,
            voice_clone_prompt=voice_clone_prompt,
            instruct=instruct,
            temperature=temperature, top_p=top_p,
        )
    elif voice.mode == "custom":
        model = get_model("custom")
        audio, sr = model.generate_custom_voice(
            text=text, speaker=voice.speaker, language=language,
            instruct=instruct, temperature=temperature, top_p=top_p,
        )
    elif voice.mode == "design":
        model = get_model("design")
        audio, sr = model.generate_voice_design(
            text=text, instruct=voice.instruct, language=language,
            temperature=temperature, top_p=top_p,
        )
    else:
        raise ValueError(f"unknown voice mode: {voice.mode}")
    return to_wav(audio, sr)

def add_natural_tail(audio: np.ndarray, sr: int, tail_ms: int = 250) -> np.ndarray:
    """Pad the end of audio with matched ambient noise so chunk transitions
    don't have abrupt silence cliffs."""
    # Sample the last 100ms to estimate ambient level
    last_samples = int(sr * 0.1)
    if len(audio) < last_samples:
        return audio
    # Estimate noise floor from quietest 20% of the tail
    tail = audio[-last_samples:]
    sorted_abs = np.sort(np.abs(tail))
    noise_level = sorted_abs[int(len(sorted_abs) * 0.2)] * 0.6  # gentle floor
    # Generate matched white noise tail
    tail_samples = int(sr * tail_ms / 1000)
    tail_noise = np.random.normal(0, noise_level, tail_samples).astype(np.float32)
    # Fade in/out so it joins smoothly
    fade = int(sr * 0.02)  # 20ms fade
    if fade > 0 and len(tail_noise) > 2 * fade:
        ramp_in = np.linspace(0, 1, fade)
        ramp_out = np.linspace(1, 0, fade)
        tail_noise[:fade] *= ramp_in
        tail_noise[-fade:] *= ramp_out
    return np.concatenate([audio, tail_noise])

app = FastAPI()

# ============== OpenAI-compatible endpoint ==============
class OpenAISpeechRequest(BaseModel):
    model: str
    input: str
    voice: str
    response_format: str = "wav"

@app.post("/v1/audio/speech")
def openai_speech(req: OpenAISpeechRequest):
    voice = store.get(req.voice)
    if not voice:
        raise HTTPException(404, f"unknown voice '{req.voice}'. Available: {store.list_names()}")
    audio = synthesize(voice, req.input)
    return Response(content=audio, media_type=f"audio/{req.response_format}")

@app.get("/v1/audio/voices")
def openai_voices():
    return {"voices": store.list_names()}

@app.get("/v1/models")
def openai_models():
    return {"data": [{"id": "tts-1", "object": "model"}]}

# ============== Rich API for playground ==============
class GenerateRequest(BaseModel):
    voice: str
    text: str
    # Optional per-request overrides — anything in voice.yaml can be overridden here
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    instruct: Optional[str] = None
    language: Optional[str] = None

@app.post("/tts/generate")
def tts_generate(req: GenerateRequest):
    voice = store.get(req.voice)
    if not voice:
        raise HTTPException(404, f"unknown voice '{req.voice}'")
    overrides = req.model_dump(exclude_none=True, exclude={"voice", "text"})
    audio = synthesize(voice, req.text, overrides=overrides)
    return Response(content=audio, media_type="audio/wav")

@app.get("/tts/voices")
def list_voices():
    return store.list_voices()

@app.get("/tts/voices/{name}")
def get_voice(name: str):
    v = store.get(name)
    if not v:
        raise HTTPException(404)
    return {k: v for k, v in v.__dict__.items() if k != "dir"}

@app.post("/tts/voices/{name}/save")
def save_voice_recipe(name: str, body: dict):
    """Save voice metadata (without changing the ref_audio file)."""
    existing = store.get(name)
    data = {**(existing.__dict__ if existing else {}), **body, "name": name}
    data.pop("dir", None)
    data.pop("speaker_pt", None)
    v = Voice(**data)
    store.save_voice(v)
    # If parameters changed in a way that affects embedding, drop the cache
    cached = store.root / name / "speaker.pt"
    if cached.exists() and existing and (
        existing.ref_audio != v.ref_audio or existing.xvec_only != v.xvec_only
    ):
        cached.unlink()
    return {"ok": True}

@app.post("/tts/voices/{name}/upload_audio")
def upload_ref_audio(name: str, file: UploadFile = File(...), ref_text: str = Form(""),
                     xvec_only: bool = Form(True), description: str = Form("")):
    """Create or replace a clone voice with new reference audio."""
    voice = Voice(
        name=name, mode="clone",
        ref_audio="ref_audio.wav", ref_text=ref_text,
        xvec_only=xvec_only, description=description,
    )
    audio_bytes = file.file.read()
    store.save_voice(voice, ref_audio_bytes=audio_bytes)
    # Drop any old embedding cache
    cached = store.root / name / "speaker.pt"
    if cached.exists():
        cached.unlink()
    return {"ok": True, "voice": name}

@app.post("/tts/reload")
def reload():
    store.reload()
    return {"voices": store.list_names()}
