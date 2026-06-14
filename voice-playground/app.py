import os
import io
import requests
import gradio as gr
import soundfile as sf

TTS_BASE = os.getenv("TTS_BASE", "http://qwen3-tts:8000")


def list_voices():
    try:
        return [v["name"] for v in requests.get(f"{TTS_BASE}/tts/voices", timeout=5).json()]
    except Exception as e:
        print(f"failed to list voices: {e}")
        return []


def get_voice(name):
    return requests.get(f"{TTS_BASE}/tts/voices/{name}", timeout=5).json()


def load_voice_defaults(name):
    if not name:
        return 0.7, 0.95, ""
    try:
        v = get_voice(name)
        return v.get("temperature", 0.7), v.get("top_p", 0.95), v.get("instruct") or ""
    except Exception:
        return 0.7, 0.95, ""


def gen(voice, text, temperature, top_p, instruct):
    if not voice or not text.strip():
        return None
    r = requests.post(f"{TTS_BASE}/tts/generate", json={
        "voice": voice, "text": text,
        "temperature": temperature, "top_p": top_p,
        "instruct": instruct or None,
    }, timeout=300)
    r.raise_for_status()
    audio, sr = sf.read(io.BytesIO(r.content))
    return (sr, audio)


def save_overrides(name, temperature, top_p, instruct):
    if not name:
        return "Pick a voice first"
    requests.post(f"{TTS_BASE}/tts/voices/{name}/save", json={
        "temperature": temperature, "top_p": top_p,
        "instruct": instruct or None,
    }, timeout=10).raise_for_status()
    return f"Saved defaults for '{name}'"


def upload_voice(name, description, audio_path, ref_text, xvec_only):
    if not name or not audio_path:
        return "Name and audio file are required"
    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/wav")}
        data = {
            "ref_text": ref_text,
            "xvec_only": str(xvec_only).lower(),
            "description": description,
        }
        r = requests.post(
            f"{TTS_BASE}/tts/voices/{name}/upload_audio",
            files=files, data=data, timeout=120,
        )
    r.raise_for_status()
    return f"Created voice '{name}'"


def create_design_voice(name, description, instruct, language, temperature, top_p):
    if not name or not instruct:
        return "Name and instruction are required"
    requests.post(f"{TTS_BASE}/tts/voices/{name}/save", json={
        "mode": "design",
        "description": description,
        "instruct": instruct,
        "language": language or "English",
        "temperature": temperature,
        "top_p": top_p,
    }, timeout=10).raise_for_status()
    return f"Created design voice '{name}'"


with gr.Blocks(title="Voice Library", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Voice Library\nTune voices, save the recipe, use them everywhere.")

    with gr.Tab("Test & Tune"):
        with gr.Row():
            voice_dd = gr.Dropdown(choices=list_voices(), label="Voice", scale=4)
            refresh = gr.Button("🔄 Refresh", scale=1)

        text = gr.Textbox(
            label="Text",
            lines=3,
            value="The future belongs to those who automate the boring bits.",
        )
        with gr.Row():
            temp = gr.Slider(0.0, 1.5, 0.7, step=0.05, label="Temperature")
            top_p = gr.Slider(0.1, 1.0, 0.95, step=0.05, label="Top-p")
        instruct = gr.Textbox(
            label="Instruction (optional override)",
            placeholder="e.g. 'in a low conspiratorial whisper'",
        )

        with gr.Row():
            gen_btn = gr.Button("Generate", variant="primary")
            save_btn = gr.Button("Save as defaults")

        audio_out = gr.Audio(label="Output", type="numpy")
        status = gr.Textbox(label="Status", interactive=False)

        voice_dd.change(load_voice_defaults, [voice_dd], [temp, top_p, instruct])
        gen_btn.click(gen, [voice_dd, text, temp, top_p, instruct], audio_out)
        save_btn.click(save_overrides, [voice_dd, temp, top_p, instruct], status)
        refresh.click(lambda: gr.update(choices=list_voices()), outputs=[voice_dd])

    with gr.Tab("Create from Audio (Clone)"):
        with gr.Row():
            with gr.Column():
                new_name = gr.Textbox(label="Voice name (becomes folder name)")
                new_desc = gr.Textbox(label="Description")
                new_audio = gr.Audio(
                    label="Reference clip (~10s, clean, no music)",
                    sources=["upload", "microphone"],
                    type="filepath",
                )
                new_text = gr.Textbox(
                    label="Reference transcript (leave empty for x-vector mode)",
                    lines=2,
                )
                new_xvec = gr.Checkbox(
                    label="x-vector only (faster, cleaner language switching)",
                    value=True,
                )
                create_btn = gr.Button("Create voice", variant="primary")
            with gr.Column():
                create_status = gr.Textbox(label="Status", interactive=False)
        create_btn.click(
            upload_voice,
            [new_name, new_desc, new_audio, new_text, new_xvec],
            create_status,
        )

    with gr.Tab("Create from Description (Design)"):
        gr.Markdown(
            "Design-mode voices are synthesized from a text description. "
            "Each generation varies slightly — for a stable persona, design "
            "once, capture a sample, then clone from that sample."
        )
        with gr.Row():
            with gr.Column():
                d_name = gr.Textbox(label="Voice name")
                d_desc = gr.Textbox(label="Description")
                d_instruct = gr.Textbox(
                    label="Voice description (instruction)",
                    lines=3,
                    placeholder="e.g. 'Warm British narrator, mid-tempo, slight gravel'",
                )
                d_lang = gr.Textbox(label="Language", value="English")
                d_temp = gr.Slider(0.0, 1.5, 0.7, step=0.05, label="Temperature")
                d_top_p = gr.Slider(0.1, 1.0, 0.95, step=0.05, label="Top-p")
                d_btn = gr.Button("Create design voice", variant="primary")
            with gr.Column():
                d_status = gr.Textbox(label="Status", interactive=False)
        d_btn.click(
            create_design_voice,
            [d_name, d_desc, d_instruct, d_lang, d_temp, d_top_p],
            d_status,
        )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
