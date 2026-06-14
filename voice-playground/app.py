# voice-playground/app.py
import os
import io
import requests
import gradio as gr
import soundfile as sf
import numpy as np

TTS = os.getenv("TTS_BASE", "http://qwen3-tts:8000")


def list_voices(mode_filter=None):
    """List voices, optionally filtered by mode (clone/design/custom)."""
    try:
        voices = requests.get(f"{TTS}/tts/voices", timeout=5).json()
        if mode_filter:
            voices = [v for v in voices if v.get("mode") == mode_filter]
        return [v["name"] for v in voices]
    except Exception as e:
        print(f"failed to list voices: {e}")
        return []


def get_voice(name):
    return requests.get(f"{TTS}/tts/voices/{name}", timeout=5).json()


def load_voice_defaults(name):
    if not name:
        return 0.7, 0.95, "", ""
    try:
        v = get_voice(name)
        return (v.get("temperature", 0.7),
                v.get("top_p", 0.95),
                v.get("instruct") or "",
                v.get("mode", "unknown"))
    except Exception:
        return 0.7, 0.95, "", "unknown"


def gen_existing(voice, text, temperature, top_p, instruct):
    """Generate using an existing voice from the library."""
    if not voice or not text.strip():
        return None, None
    r = requests.post(f"{TTS}/tts/generate", json={
        "voice": voice, "text": text,
        "temperature": temperature, "top_p": top_p,
        "instruct": instruct or None,
    }, timeout=300)
    r.raise_for_status()
    wav_bytes = r.content
    audio, sr = sf.read(io.BytesIO(wav_bytes))
    return (sr, audio), wav_bytes


def gen_inline_design(instruct, text, language, temperature, top_p):
    """Generate using an ad-hoc design voice (not saved to library)."""
    if not instruct or not text.strip():
        return None, None
    # Create a temporary design voice, generate, then delete? 
    # Simpler: hit the TTS server with a one-shot design generation.
    # Since the rich API requires a saved voice, we save under a temp name,
    # generate, then leave it (user can rename or delete later).
    temp_name = "_design_scratch"
    requests.post(f"{TTS}/tts/voices/{temp_name}/save", json={
        "mode": "design",
        "instruct": instruct,
        "language": language or "English",
        "temperature": temperature,
        "top_p": top_p,
        "description": "Scratch pad for design tuning (auto-managed)",
    }, timeout=10).raise_for_status()
    
    r = requests.post(f"{TTS}/tts/generate", json={
        "voice": temp_name, "text": text,
    }, timeout=300)
    r.raise_for_status()
    wav_bytes = r.content
    audio, sr = sf.read(io.BytesIO(wav_bytes))
    return (sr, audio), wav_bytes


def promote_to_clone(new_name, description, ref_text, xvec_only, wav_bytes):
    """Take the last-generated audio and save it as a new clone voice."""
    if not new_name:
        return "❌ Name is required"
    if not wav_bytes:
        return "❌ Generate audio first, then promote"
    if not ref_text:
        return "❌ Reference text is required for the clone"
    
    files = {"file": ("ref_audio.wav", wav_bytes, "audio/wav")}
    data = {
        "ref_text": ref_text,
        "xvec_only": str(xvec_only).lower(),
        "description": description or f"Promoted from design ({new_name})",
    }
    r = requests.post(
        f"{TTS}/tts/voices/{new_name}/upload_audio",
        files=files, data=data, timeout=120,
    )
    r.raise_for_status()
    return f"✅ Created clone voice '{new_name}' — now available in OpenWebUI and all clients"


def save_overrides(name, temperature, top_p, instruct):
    if not name:
        return "Pick a voice first"
    requests.post(f"{TTS}/tts/voices/{name}/save", json={
        "temperature": temperature, "top_p": top_p,
        "instruct": instruct or None,
    }, timeout=10).raise_for_status()
    return f"Saved defaults for '{name}'"


def upload_clone(name, description, audio_path, ref_text, xvec_only):
    if not name or not audio_path:
        return "Name and audio file are required"
    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/wav")}
        data = {"ref_text": ref_text,
                "xvec_only": str(xvec_only).lower(),
                "description": description}
        r = requests.post(
            f"{TTS}/tts/voices/{name}/upload_audio",
            files=files, data=data, timeout=120,
        )
    r.raise_for_status()
    return f"Created voice '{name}'"


with gr.Blocks(title="Voice Library", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Voice Library\nTune voices, save the recipe, use them everywhere.")

    # State to hold the last-generated audio bytes across tabs
    last_wav = gr.State(value=None)

    # ==================== TEST & TUNE ====================
    with gr.Tab("Test & Tune"):
        gr.Markdown("Pick an existing voice. Tune parameters. Save defaults — or freeze "
                    "the current settings as a brand-new clone voice via 'Promote'.")
        with gr.Row():
            voice_dd = gr.Dropdown(choices=list_voices(), label="Voice", scale=4)
            voice_mode = gr.Textbox(label="Mode", interactive=False, scale=1)
            refresh = gr.Button("🔄", scale=1)

        text = gr.Textbox(label="Text", lines=3,
                          value="The future belongs to those who automate the boring bits.")
        with gr.Row():
            temp = gr.Slider(0.0, 1.5, 0.7, step=0.05, label="Temperature")
            top_p = gr.Slider(0.1, 1.0, 0.95, step=0.05, label="Top-p")
        instruct = gr.Textbox(label="Instruction (optional override)",
                              placeholder="e.g. 'in a low conspiratorial whisper'")

        with gr.Row():
            gen_btn = gr.Button("Generate", variant="primary")
            save_btn = gr.Button("Save as defaults")

        audio_out = gr.Audio(label="Output", type="numpy")
        status = gr.Textbox(label="Status", interactive=False)

        gr.Markdown("### Promote current take to a clone voice")
        gr.Markdown(
            "If you like the take above and want to lock it in as a stable voice "
            "(no more drift between generations), promote it. The clone uses the "
            "audio you just heard as its reference, so future generations match exactly."
        )
        with gr.Row():
            promote_name = gr.Textbox(label="New clone voice name",
                                       placeholder="e.g. 'jarvis-formal' or 'narrator-warm'")
            promote_xvec = gr.Checkbox(label="x-vector only (stable, recommended)", value=True)
        promote_desc = gr.Textbox(label="Description (optional)")
        promote_ref_text = gr.Textbox(label="Reference text (what was spoken — should match Text above)",
                                       value="")
        promote_btn = gr.Button("⬆ Promote to Clone Voice", variant="primary")
        promote_status = gr.Textbox(label="Status", interactive=False)

        # Wire it up
        voice_dd.change(load_voice_defaults, [voice_dd], [temp, top_p, instruct, voice_mode])
        gen_btn.click(
            gen_existing,
            [voice_dd, text, temp, top_p, instruct],
            [audio_out, last_wav],
        )
        # When user types text, auto-fill the promote reference text
        text.change(lambda t: t, [text], [promote_ref_text])
        save_btn.click(save_overrides, [voice_dd, temp, top_p, instruct], status)
        promote_btn.click(
            promote_to_clone,
            [promote_name, promote_desc, promote_ref_text, promote_xvec, last_wav],
            promote_status,
        )
        refresh.click(lambda: gr.update(choices=list_voices()), outputs=[voice_dd])

    # ==================== DESIGN → CLONE WORKFLOW ====================
    with gr.Tab("Design a New Persona"):
        gr.Markdown(
            "Design a new voice from a text description, tune it, then lock it in "
            "as a clone voice. This is the recommended workflow for stable AI "
            "personas like Jarvis — design mode varies per call, but a clone voice "
            "frozen from a designed sample stays consistent forever."
        )
        with gr.Row():
            with gr.Column():
                d_instruct = gr.Textbox(
                    label="Voice description",
                    lines=3,
                    value="A calm, measured, articulate British male voice with a hint of dry wit",
                )
                d_text = gr.Textbox(
                    label="Test text",
                    lines=3,
                    value="Good evening, sir. Shall I prepare the usual?",
                )
                d_lang = gr.Textbox(label="Language", value="English")
                d_temp = gr.Slider(0.0, 1.5, 0.7, step=0.05, label="Temperature")
                d_top_p = gr.Slider(0.1, 1.0, 0.95, step=0.05, label="Top-p")
                d_gen_btn = gr.Button("Generate sample", variant="primary")
            with gr.Column():
                d_audio = gr.Audio(label="Sample", type="numpy")
                gr.Markdown(
                    "Don't like it? Tweak the description or temperature and regenerate. "
                    "Each call gives a different rendering. Keep going until one sounds right."
                )

        gr.Markdown("### Promote this sample to a permanent clone voice")
        with gr.Row():
            d_name = gr.Textbox(label="Clone voice name",
                                 placeholder="e.g. 'jarvis'")
            d_xvec = gr.Checkbox(label="x-vector only (stable)", value=True)
        d_desc = gr.Textbox(label="Description (optional)")
        d_promote_btn = gr.Button("⬆ Promote to Clone Voice", variant="primary")
        d_promote_status = gr.Textbox(label="Status", interactive=False)

        d_gen_btn.click(
            gen_inline_design,
            [d_instruct, d_text, d_lang, d_temp, d_top_p],
            [d_audio, last_wav],
        )
        d_promote_btn.click(
            promote_to_clone,
            [d_name, d_desc, d_text, d_xvec, last_wav],  # reuse d_text as ref_text
            d_promote_status,
        )

    # ==================== CREATE FROM AUDIO (existing) ====================
    with gr.Tab("Create from Audio (Clone)"):
        gr.Markdown("Already have a reference clip? Drop it in here.")
        with gr.Row():
            with gr.Column():
                c_name = gr.Textbox(label="Voice name")
                c_desc = gr.Textbox(label="Description")
                c_audio = gr.Audio(
                    label="Reference clip (~10s, clean, no music)",
                    sources=["upload", "microphone"],
                    type="filepath",
                )
                c_text = gr.Textbox(
                    label="Reference transcript (optional for x-vector mode)",
                    lines=2,
                )
                c_xvec = gr.Checkbox(
                    label="x-vector only (faster, cleaner)",
                    value=True,
                )
                c_btn = gr.Button("Create voice", variant="primary")
            with gr.Column():
                c_status = gr.Textbox(label="Status", interactive=False)
        c_btn.click(upload_clone,
                    [c_name, c_desc, c_audio, c_text, c_xvec], c_status)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)