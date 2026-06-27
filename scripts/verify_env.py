#!/usr/bin/env python3
"""verify_env.py — preflight check for the memory-pruning thesis run.

Backs ``make verify-env``. Prints a PASS/WARN/FAIL table for every prerequisite
and exits non-zero if any HARD prerequisite is missing. HARD = needed for the
code to import/construct at all; WARN = needed for a real run but not for import
(so the failure mode is clear rather than a mid-run crash).

Run after ``make setup`` and after pasting the Ollama key into ``.env``.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GREEN, YELLOW, RED, RESET = "\033[1;32m", "\033[1;33m", "\033[1;31m", "\033[0m"

results: list[tuple[str, str, str]] = []  # (status, name, detail)


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))


def hard(name: str, ok: bool, detail_ok: str = "", detail_bad: str = "") -> None:
    record("PASS" if ok else "FAIL", name, detail_ok if ok else detail_bad)


def soft(name: str, ok: bool, detail_ok: str = "", detail_bad: str = "") -> None:
    record("PASS" if ok else "WARN", name, detail_ok if ok else detail_bad)


# --- HARD checks ------------------------------------------------------------
v = sys.version_info
hard("python >= 3.10", v >= (3, 10), f"{v.major}.{v.minor}.{v.micro}", f"{v.major}.{v.minor} too old")

try:
    import faiss  # noqa: F401
    hard("faiss importable", True)
except Exception as e:  # pragma: no cover - env dependent
    hard("faiss importable", False, detail_bad=str(e))

curriculum = ROOT / "data" / "SWE-Bench-CL-Curriculum.json"
hard("curriculum present", curriculum.exists(), str(curriculum), f"missing: {curriculum} (run scripts/build_curriculum.py)")

env_file = ROOT / ".env"
hard(".env present", env_file.exists(), str(env_file), "missing: cp .env.example .env")

# Load .env (so the key check reflects the real runtime config).
try:
    from dotenv import load_dotenv

    load_dotenv(env_file)
except Exception:
    pass
chat_key = os.environ.get("LLM_CHAT_API_KEY", "").strip()
hard("LLM_CHAT_API_KEY set", bool(chat_key), "set", "empty — paste your Ollama Cloud key into .env")

try:
    from src.config.loader import load_config

    cfg = load_config()
    hard("config loads", isinstance(cfg, dict) and "memory" in cfg)
except Exception as e:
    hard("config loads", False, detail_bad=str(e))

# --- SOFT checks (needed for a real run, not for import) --------------------
soft("docker CLI", shutil.which("docker") is not None, detail_bad="install Docker (eval harness needs it)")

soft("ollama CLI", shutil.which("ollama") is not None, detail_bad="install Ollama (local embedder daemon)")

# swebench + datasets are the eval-stage deps (Phase 5/6).
for mod in ("swebench", "datasets"):
    try:
        __import__(mod)
        soft(f"{mod} importable", True)
    except Exception:
        soft(f"{mod} importable", False, detail_bad=f"pip install {mod} (run `make setup`)")

# Live embedder reachability (best-effort; needs the local daemon up).
try:
    from src.config import llm_factory as f

    client = f.get_embedding_client()
    dim = len(client.embeddings.create(model=f.embedding_model(), input="ping").data[0].embedding)
    expected = f.embedding_dim()
    soft(
        "embedder reachable",
        dim == expected,
        f"dim={dim}",
        f"dim {dim} != configured {expected} (rebuild FAISS or fix EMBEDDING_DIM)",
    )
except Exception as e:
    soft(
        "embedder reachable",
        False,
        detail_bad=(
            f"{type(e).__name__}: REQUIRED for 5/6 policies (only NoMemory runs without it) "
            "— start `ollama serve` + `ollama pull nomic-embed-text-v2-moe` before `make pilot`"
        ),
    )

# --- report -----------------------------------------------------------------
print("\nEnvironment verification:\n")
width = max(len(n) for _, n, _ in results)
n_fail = 0
for status, name, detail in results:
    color = {"PASS": GREEN, "WARN": YELLOW, "FAIL": RED}[status]
    n_fail += status == "FAIL"
    print(f"  {color}{status:4}{RESET}  {name:<{width}}  {detail}")

print()
if n_fail:
    print(f"{RED}{n_fail} hard prerequisite(s) missing — fix before running.{RESET}")
    sys.exit(1)
warns = sum(s == "WARN" for s, _, _ in results)
if warns:
    print(f"{YELLOW}{warns} warning(s): import-clean, but a full run needs these (Docker, Ollama daemon, swebench).{RESET}")
print(f"{GREEN}All hard prerequisites satisfied.{RESET}")
sys.exit(0)
