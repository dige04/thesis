#!/usr/bin/env bash
# setup_env.sh — idempotent environment bootstrap for the memory-pruning thesis.
#
# Goal (build-to-pilot DoD): after a fresh clone, a user fills the Ollama key in
# .env and runs `make setup`, and the repo is ready to `make verify-env` then
# `make smoke` / `make pilot`. Everything that CAN be automated is automated
# here; the only manual step is pasting the Ollama Cloud API key into .env.
#
# Safe to re-run. Optional steps (ollama / docker) warn but never abort.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY=python3
VENV=.venv
EMBED_MODEL="${EMBEDDING_MODEL:-nomic-embed-text-v2-moe}"
CURRICULUM="data/SWE-Bench-CL-Curriculum.json"

say() { printf '\033[1;34m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[setup:warn]\033[0m %s\n' "$*"; }

# 1. venv + deps -------------------------------------------------------------
if [ ! -x "$VENV/bin/python" ]; then
  say "Creating virtualenv at $VENV"
  "$PY" -m venv "$VENV"
fi
say "Installing project + dev + swebench deps (editable)"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -e ".[dev]"

# 2. .env --------------------------------------------------------------------
if [ ! -f .env ]; then
  say "Creating .env from .env.example (FILL IN LLM_CHAT_API_KEY)"
  cp .env.example .env
else
  say ".env already present (leaving as-is)"
fi

# 3. dataset / curriculum ----------------------------------------------------
if [ ! -f "$CURRICULUM" ]; then
  say "Building curriculum -> $CURRICULUM"
  "$VENV/bin/python" scripts/build_curriculum.py || warn "curriculum build failed (needs network); run scripts/build_curriculum.py later"
else
  say "Curriculum present ($CURRICULUM)"
fi

# 4. local Ollama embedder (D2) ---------------------------------------------
if command -v ollama >/dev/null 2>&1; then
  if ollama list 2>/dev/null | grep -q "$EMBED_MODEL"; then
    say "Ollama embedder '$EMBED_MODEL' already pulled"
  else
    say "Pulling Ollama embedder '$EMBED_MODEL' (local; Ollama Cloud has no embedder)"
    ollama pull "$EMBED_MODEL" || warn "could not pull $EMBED_MODEL; ensure 'ollama serve' is running"
  fi
else
  warn "ollama CLI not found — install Ollama + run 'ollama serve' + 'ollama pull $EMBED_MODEL' (embeddings need a LOCAL daemon)"
fi

# 5. Docker (eval harness images are built on demand by the build-probe) -----
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  say "Docker daemon reachable (swebench arm64 instance images build on demand via 'make build-probe')"
else
  warn "Docker not available — eval (swebench harness) needs Docker. Install Docker Desktop and enable it."
fi

say "Done. Next:  1) put your key in .env (LLM_CHAT_API_KEY)   2) make verify-env   3) make smoke"
