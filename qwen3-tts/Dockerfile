# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=nvcr.io/nvidia/l4t-pytorch:r36.4.0-py1
FROM ${BASE_IMAGE}

ARG FASTER_QWEN3_TTS_REF=0.2.6
ARG TRANSFORMERS_VERSION=4.57.3
ARG TORCHAUDIO_VERSION=2.9.1

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models \
    HF_HUB_ENABLE_HF_TRANSFER=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        sox \
        libsox-fmt-all \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN git clone --depth=1 --branch ${FASTER_QWEN3_TTS_REF} \
        https://github.com/andimarafioti/faster-qwen3-tts.git . \
    || git clone --depth=1 https://github.com/andimarafioti/faster-qwen3-tts.git .

# Generate clean version-pinned constraints from the NGC-installed torch stack.
# We read metadata directly because NGC installs torch from a local wheel that
# pip freeze emits as a file:// reference (which constraints files reject).
COPY <<'EOF' /tmp/make-pins.py
import importlib.metadata as m
keep_prefixes = ("torchaudio", "torchvision", "triton", "nvidia-", "cuda-")
for d in m.distributions():
    name = d.metadata["Name"]
    if not name:
        continue
    lname = name.lower()
    if lname == "torch" or lname.startswith(keep_prefixes):
        print(f"{name}=={d.version}")
EOF
RUN python /tmp/make-pins.py > /tmp/ngc-pins.txt && cat /tmp/ngc-pins.txt

RUN pip install --no-cache-dir --no-build-isolation \
        -c /tmp/ngc-pins.txt \
        -e ".[demo]" \
 && pip install --no-cache-dir -c /tmp/ngc-pins.txt \
        hf_transfer

RUN pip install --no-cache-dir -c /tmp/ngc-pins.txt --upgrade torchao

RUN pip install --no-cache-dir -c /tmp/ngc-pins.txt \
        "transformers==${TRANSFORMERS_VERSION}" \
	pyyaml

RUN pip install --force-reinstall --no-deps --no-cache-dir \
        "torchaudio==${TORCHAUDIO_VERSION}" \
        --index-url https://download.pytorch.org/whl/cu130

# Demo UI uses nano-parakeet for auto-transcribing reference audio uploads
RUN pip install --no-cache-dir -c /tmp/ngc-pins.txt nano-parakeet

RUN python -c "import torch, torchaudio; print('torch', torch.__version__, 'torchaudio', torchaudio.__version__)" \
 && python -c "import torchaudio.compliance.kaldi" \
 && python -c "from faster_qwen3_tts import FasterQwen3TTS; print('faster_qwen3_tts OK')"

RUN cp /app/ref_audio.wav /app/default_ref.wav

COPY voice_store.py /app/voice_store.py
COPY tts_server.py  /app/tts_server.py

EXPOSE 8000

CMD ["uvicorn", "tts_server:app", "--host", "0.0.0.0", "--port", "8000"]
