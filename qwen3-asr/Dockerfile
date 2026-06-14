# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=nvcr.io/nvidia/l4t-pytorch:r36.4.0-py1
FROM ${BASE_IMAGE}

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
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Generate clean version-pinned constraints from the NGC-installed torch stack.
# NGC installs torch from a local wheel path that pip freeze emits as a
# file:// reference (which constraints files reject), so we read metadata directly.
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

# Now the constraints file exists; rest of installs reference it.
RUN pip install --no-cache-dir --no-build-isolation \
        -c /tmp/ngc-pins.txt \
        qwen-asr \
        fastapi \
        'uvicorn[standard]' \
        python-multipart \
 && pip install --no-cache-dir -c /tmp/ngc-pins.txt \
        hf_transfer

# Upgrade torchao to fix the torchao.prototype.safetensors import that
# transformers' quantizer registration uses at import time.
RUN pip install --no-cache-dir -c /tmp/ngc-pins.txt --upgrade torchao

# torchaudio gets pulled forward by transformers; force it back to a
# version with ABI matching NGC's torch 2.9 (same fix as the TTS container).
RUN pip install --force-reinstall --no-deps --no-cache-dir \
        "torchaudio==${TORCHAUDIO_VERSION}" \
        --index-url https://download.pytorch.org/whl/cu130

# Build-time sanity check — fail loudly if anything's wrong before runtime.
RUN python -c "import torch, torchaudio; print('torch', torch.__version__, 'torchaudio', torchaudio.__version__)" \
 && python -c "import torchaudio.compliance.kaldi" \
 && python -c "from qwen_asr import Qwen3ASRModel; print('qwen_asr OK')"

COPY asr_server.py /app/asr_server.py

EXPOSE 8000
CMD ["uvicorn", "asr_server:app", "--host", "0.0.0.0", "--port", "8000"]
