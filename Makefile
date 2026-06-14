# ==============================================================================
# Makefile for building and publishing qwen3-audio-gb10 containers
# ==============================================================================
#
# Targets:
#   make build         — Build all images (unified audio + playground)
#   make build-audio   — Build qwen3-audio-gb10 (unified ASR+TTS image)
#   make build-play    — Build voice-playground only
#   make push          — Push all images to ghcr.io
#   make push-audio    — Push qwen3-audio-gb10 to ghcr.io
#   make push-play     — Push voice-playground to ghcr.io
#   make push-one=AUDIO|PLAY — Push a single image
#   make clean         — Remove built images
#   make help          — Show this help
#
# Variables (override on command line, e.g. make PUSH_REPO=ghcr.io/myorg):
#   PUSH_REPO   — Target registry prefix (default: ghcr.io/cjlapao)
#   VERSION     — Image version tag (default: git short SHA)
#
# Prerequisites:
#   - Docker installed and running
#   - Logged into ghcr.io:  docker login ghcr.io -u <user> -p <token>
#   - NVIDIA GPU + nvidia-container-toolkit (for audio image)
# ==============================================================================

# ── Registry & version ────────────────────────────────────────────────────────

PUSH_REPO   ?= ghcr.io/cjlapao
VERSION     ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "dev")

# ── Image definitions ─────────────────────────────────────────────────────────

AUDIO_DIR   := .
PLAY_DIR    := voice-playground

AUDIO_NAME  := $(PUSH_REPO)/qwen3-audio-gb10
PLAY_NAME   := $(PUSH_REPO)/voice-playground

# ── Audio build args ──────────────────────────────────────────────────────────

AUDIO_ARGS  := \
	--build-arg FASTER_QWEN3_TTS_REF=0.2.6 \
	--build-arg TRANSFORMERS_VERSION=4.57.3 \
	--build-arg TORCHAUDIO_VERSION=2.9.1

# ── Helper: tag & push helper ─────────────────────────────────────────────────
# Usage: $(call tag_and_push,NAME,TAG,DEST_NAME)
#   NAME:TAG → DEST_NAME:TAG, then DEST_NAME:TAG → DEST_NAME:latest
# ──────────────────────────────────────────────────────────────────────────────

define tag_and_push
	docker tag $(1):$(2) $(3):$(2)
	docker push $(3):$(2)
	docker tag $(3):$(2) $(3):latest
	docker push $(3):latest
endef

# ── Build targets ─────────────────────────────────────────────────────────────

.PHONY: build build-audio build-play clean help push push-audio push-play push-one

build: build-audio build-play
	@echo ""
	@echo "=== All images built successfully ==="
	@echo "  $(AUDIO_NAME):$(VERSION)"
	@echo "  $(PLAY_NAME):$(VERSION)"

build-audio:
	@echo ">>> Building $(AUDIO_NAME):$(VERSION) ..."
	docker build $(AUDIO_ARGS) -t $(AUDIO_NAME):$(VERSION) $(AUDIO_DIR)
	@echo ">>> Done: $(AUDIO_NAME):$(VERSION)"

build-play:
	@echo ">>> Building $(PLAY_NAME):$(VERSION) ..."
	docker build -t $(PLAY_NAME):$(VERSION) $(PLAY_DIR)
	@echo ">>> Done: $(PLAY_NAME):$(VERSION)"

# ── Push targets ──────────────────────────────────────────────────────────────

push: push-audio push-play
	@echo ""
	@echo "=== All images pushed to $(PUSH_REPO) ==="

push-audio:
	@echo ">>> Pushing $(AUDIO_NAME):$(VERSION) ..."
	$(call tag_and_push,$(AUDIO_NAME),$(VERSION),$(AUDIO_NAME))
	@echo ">>> Done."

push-play:
	@echo ">>> Pushing $(PLAY_NAME):$(VERSION) ..."
	$(call tag_and_push,$(PLAY_NAME),$(VERSION),$(PLAY_NAME))
	@echo ">>> Done."

# Single-image push: make push-one=AUDIO|PLAY
push-one:
	@if [ "$(ONE)" = "AUDIO" ]; then \
		echo ">>> Pushing $(AUDIO_NAME):$(VERSION) ..."; \
		$(call tag_and_push,$(AUDIO_NAME),$(VERSION),$(AUDIO_NAME)); \
		echo ">>> Done."; \
	elif [ "$(ONE)" = "PLAY" ]; then \
		echo ">>> Pushing $(PLAY_NAME):$(VERSION) ..."; \
		$(call tag_and_push,$(PLAY_NAME),$(VERSION),$(PLAY_NAME)); \
		echo ">>> Done."; \
	else \
		echo "ERROR: push-one requires ONE=AUDIO|PLAY"; \
		exit 1; \
	fi

# ── Clean ─────────────────────────────────────────────────────────────────────

clean:
	@echo ">>> Removing built images ..."
	docker rmi $(AUDIO_NAME):$(VERSION) $(AUDIO_NAME):latest 2>/dev/null || true
	docker rmi $(PLAY_NAME):$(VERSION) $(PLAY_NAME):latest 2>/dev/null || true
	@echo ">>> Done."

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build           Build all images"
	@echo "  build-audio     Build unified ASR+TTS image only"
	@echo "  build-play      Build playground image only"
	@echo "  push            Push all images to ghcr.io"
	@echo "  push-audio      Push audio image to ghcr.io"
	@echo "  push-play       Push playground to ghcr.io"
	@echo "  push-one=AUDIO  Push audio only (also: PLAY)"
	@echo "  clean           Remove built images"
	@echo "  help            Show this help"
	@echo ""
	@echo "Variables (override on command line):"
	@echo "  PUSH_REPO=<registry>   Target registry prefix (default: ghcr.io/cjlapao)"
	@echo "  VERSION=<tag>          Image version tag (default: git short SHA)"
	@echo ""
	@echo "Examples:"
	@echo "  make build                  # Build all images"
	@echo "  make build push             # Build & push all images"
	@echo "  make push-one=AUDIO         # Push audio only"
	@echo "  make VERSION=v1.0.0 build   # Build with version tag"
	@echo "  make PUSH_REPO=ghcr.io/myuser build   # Custom registry"