# ==============================================================================
# Makefile for building and publishing qwen3-asr-tts-gb10 containers
#   Multi-arch — same VERSION tag -> OCI manifest list: linux/arm64 + linux/amd64
#     Docker resolves the correct arch at pull time automatically.
# ==============================================================================

PUSH_REPO   ?= ghcr.io/cjlapao
VERSION       ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "dev")

REGISTRY_AUDIO = ghcr.io/cjlapao/qwen3-audio-gb10
REGISTRY_PLAY  = ghcr.io/cjlapao/voice-playground

AUDIO_DIR := .
PLAY_DIR  := voice-playground

# Multi-platform build requires a containerd-backed builder.
# We use --builder to pin it so it works even if "docker" is the default.
BUILD_CMD := docker buildx build --builder multi-arch-builder --platform linux/arm64,linux/amd64 --push

.PHONY: builder setup build build-audio play-build push clean help

builder:
	@echo ">>> Creating buildx builder with containerd driver..."
	docker buildx create --name multi-arch-builder --driver docker-container 2>/dev/null || true
	docker buildx inspect multi-arch-builder --bootstrap

setup: builder

build: setup build-audio play-build
	@echo ""
	@echo "*** Multi-arch build complete ***"

build-audio:
	@echo "[Audio]"
	$(BUILD_CMD) \
		--tag $(REGISTRY_AUDIO):$(VERSION) \
		--label="org.opencontainers.image.source=https://github.com/cjlapao/qwen3-asr-tts-gb10" \
		--label="org.opencontainers.image.description=Qwen3 Audio GB10 ASR+TTS unified container" \
		--build-arg FASTER_QWEN3_TTS_REF=0.2.6 \
		--build-arg TRANSFORMERS_VERSION=4.57.3 \
		--build-arg TORCHAUDIO_VERSION=2.9.1 \
		$(AUDIO_DIR)

play-build:
	@echo "[Playground]"
	$(BUILD_CMD) \
		--tag $(REGISTRY_PLAY):$(VERSION) \
		--label="org.opencontainers.image.source=https://github.com/cjlapao/qwen3-asr-tts-gb10" \
		$(PLAY_DIR)

push:
	@echo "*** Pushing all images ***"
	docker push $(REGISTRY_AUDIO):$(VERSION) && docker push $(REGISTRY_AUDIO):latest
	docker push $(REGISTRY_PLAY):$(VERSION) && docker push $(REGISTRY_PLAY):latest
	@echo "== All pushed =="

clean:
	@echo "--- Removing ALL cached images ---"
	docker rmi $(REGISTRY_AUDIO):$(VERSION) 2>/dev/null || true
	docker rmi $(REGISTRY_AUDIO):latest 2>/dev/null || true
	docker rmi $(REGISTRY_PLAY):$(VERSION) 2>/dev/null || true
	docker rmi $(REGISTRY_PLAY):latest 2>/dev/null || true

help:
	@echo "Usage: make [target] [VERSION=x.x.x]"
	@echo ""
	@echo "Targets:"
	@echo "  build         Build AND PUSH mult-arch (arm64+amd64) for ALL apps"
	@echo "  build-audio   Build only: audio, mult-arch (no push)"
	@echo "  play-build    Build only: playground, mult-arch (no push)"
	@echo "  push          Re-push already-built images via docker push"
	@echo "  clean         Remove ALL tagged images from local docker cache"
	@echo "  help          This help"
	@echo ""
	@echo "Multi-arch means one VERSION tag produces an OCI manifest list"
	@echo "bundling BOTH arm64 and amd64 layers. Docker picks the right one."
	@echo ""
	@echo "Examples:"
	@echo "  make build                      # Build + Push all mult-arch"
	@echo "  make VERSION=v2.1.0 build       # Tag v2.1.0 instead of git SHA"
	@echo "  make push                       # Push again (images must be built first)"
