# voice_store.py
import os
import yaml
import torch
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

VOICES_ROOT = Path(os.getenv("VOICES_ROOT", "/app/voices"))

@dataclass
class Voice:
    name: str
    mode: str                          # "clone" | "custom" | "design"
    description: str = ""
    language: str = "English"
    # Clone-mode fields
    ref_audio: Optional[str] = None
    ref_text: str = ""
    xvec_only: bool = True
    speaker_pt: Optional[str] = None   # path to cached embedding
    # Custom-mode field
    speaker: Optional[str] = None      # preset speaker id
    # Design-mode field
    instruct: Optional[str] = None
    # Generation defaults
    temperature: float = 0.7
    top_p: float = 0.95
    non_streaming_mode: Optional[bool] = None
    append_silence: bool = True
    # Internal
    dir: Optional[Path] = field(default=None, repr=False)


class VoiceStore:
    def __init__(self, root: Path = VOICES_ROOT):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._voices: dict[str, Voice] = {}
        self.reload()

    def reload(self) -> dict[str, Voice]:
        self._voices.clear()
        for d in sorted(self.root.iterdir()):
            if not d.is_dir(): continue
            yaml_path = d / "voice.yaml"
            if not yaml_path.exists(): continue
            try:
                data = yaml.safe_load(yaml_path.read_text())
                # Resolve relative paths inside the voice's own folder
                if data.get("ref_audio"):
                    data["ref_audio"] = str(d / data["ref_audio"])
                speaker_pt = d / "speaker.pt"
                if speaker_pt.exists():
                    data["speaker_pt"] = str(speaker_pt)
                data["dir"] = d
                self._voices[data["name"]] = Voice(**data)
            except Exception as e:
                print(f"failed to load {yaml_path}: {e}")
        return self._voices

    def get(self, name: str) -> Optional[Voice]:
        return self._voices.get(name)

    def list_names(self) -> list[str]:
        return list(self._voices.keys())

    def list_voices(self) -> list[dict]:
        return [{"name": v.name, "mode": v.mode, "description": v.description,
                 "language": v.language} for v in self._voices.values()]

    def save_voice(self, voice: Voice, ref_audio_bytes: Optional[bytes] = None) -> Voice:
        d = self.root / voice.name
        d.mkdir(exist_ok=True)
        if ref_audio_bytes:
            ref_path = d / "ref_audio.wav"
            ref_path.write_bytes(ref_audio_bytes)
            voice.ref_audio = "ref_audio.wav"  # relative for storage
        out = asdict(voice)
        out.pop("dir", None)
        out.pop("speaker_pt", None)
        # Strip the absolute path back to relative for storage
        if voice.mode == "clone" and voice.ref_audio and "/" in voice.ref_audio:
            out["ref_audio"] = Path(voice.ref_audio).name
        (d / "voice.yaml").write_text(yaml.safe_dump(out, sort_keys=False))
        self.reload()
        return self.get(voice.name)

    def cache_embedding(self, name: str, embedding: torch.Tensor) -> Path:
        d = self.root / name
        path = d / "speaker.pt"
        torch.save(embedding.detach().cpu(), path)
        self.reload()
        return path
