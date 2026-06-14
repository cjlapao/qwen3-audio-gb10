# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=nvcr.io/nvidia/pytorch:25.10-py3
FROM ${BASE_IMAGE}

ARG FASTER_QWEN3_TTS_REF=0.2.6
ARG TRANSFORMERS_VERSION=4.57.3
ARG TORCHAUDIO_VERSION=2.9.1

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models \
    HF_HUB_ENABLE_HF_TRANSFER=1 \
    VOICES_ROOT=/app/voices

# System deps for audio I/O
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        sox \
        libsox-fmt-all \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Generate clean version-pinned constraints from NGC-installed torch stack.
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

# ------------------------------------------------------------------
# faster-qwen3-tts (cloned from source, installed editable)
# ------------------------------------------------------------------
RUN git clone --depth=1 --branch ${FASTER_QWEN3_TTS_REF} \
        https://github.com/andimarafioti/faster-qwen3-tts.git /opt/faster-qwen3-tts \
    || git clone --depth=1 \
        https://github.com/andimarafioti/faster-qwen3-tts.git /opt/faster-qwen3-tts

RUN pip install --no-cache-dir --no-build-isolation \
        -c /tmp/ngc-pins.txt \
        -e /opt/faster-qwen3-tts \
 && pip install --no-cache-dir -c /tmp/ngc-pins.txt \
        hf_transfer pyyaml

# ------------------------------------------------------------------
# qwen-asr (from PyPI)
# ------------------------------------------------------------------
RUN pip install --no-cache-dir --no-build-isolation \
        -c /tmp/ngc-pins.txt \
        qwen-asr

# ------------------------------------------------------------------
# Shared web stack
# ------------------------------------------------------------------
RUN pip install --no-cache-dir -c /tmp/ngc-pins.txt \
        fastapi \
        'uvicorn[standard]' \
        python-multipart

# ------------------------------------------------------------------
# Common fixes (same ones we hit on both standalone images)
# ------------------------------------------------------------------
# torchao for transformers quantizer registration
RUN pip install --no-cache-dir -c /tmp/ngc-pins.txt --upgrade torchao

# Pin transformers to what faster-qwen3-tts and qwen-asr both work with
RUN pip install --no-cache-dir -c /tmp/ngc-pins.txt \
        "transformers==${TRANSFORMERS_VERSION}"

# Force torchaudio back to a version with ABI matching NGC's torch 2.9
RUN pip install --force-reinstall --no-deps --no-cache-dir \
        "torchaudio==${TORCHAUDIO_VERSION}" \
        --index-url https://download.pytorch.org/whl/cu130

# ------------------------------------------------------------------
# Build-time sanity check: BOTH stacks must import cleanly
# ------------------------------------------------------------------
RUN python -c "import torch, torchaudio; print('torch', torch.__version__, 'torchaudio', torchaudio.__version__)" \
 && python -c "import torchaudio.compliance.kaldi" \
 && python -c "from faster_qwen3_tts import FasterQwen3TTS; print('faster_qwen3_tts OK')" \
 && python -c "from qwen_asr import Qwen3ASRModel; print('qwen_asr OK')"

# ------------------------------------------------------------------
# Application code
# ------------------------------------------------------------------
WORKDIR /app
COPY app/ /app/

# Copy the default ref audio from the faster-qwen3-tts repo for fallback
RUN cp /opt/faster-qwen3-tts/ref_audio.wav /app/default_ref.wav

EXPOSE 8000

CMD ["python", "-u", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]