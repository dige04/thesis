<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# config

## Purpose
Configuration and provider wiring. Loads/validates/freezes the YAML config, builds the LLM/embedding clients in a provider-agnostic way (so the experiment can run on Ollama Cloud or OpenAI by editing `.env` only), and houses the calibration utilities used at the Week-4 lock. Implements v5 §13 (YAML) and the runtime deviations D1–D4 (CLAUDE.md).

## Key Files
| File | Description |
|------|-------------|
| `loader.py` | Loads `configs/base.yaml`, merges per-policy overrides from `configs/policies/`, validates, and supports **freezing** after calibration. Env vars override YAML. Req 26. |
| `llm_factory.py` | **Single source of truth for SDK clients.** Builds a chat/generative client (Ollama Cloud, `https://ollama.com/v1`) and a **separate** embedding client (local Ollama, `http://localhost:11434/v1`) from `.env`. `get_chat_client()`, `get_embedding_client()`, `main_model()`, `summary_model()`, `classifier_model()`, `embedding_model()`. **Never set a global `OPENAI_BASE_URL`** — it would redirect embeddings to a cloud endpoint with no embedder and break retrieval. |
| `calibration.py` | Post-pilot tuning (Req 30) for the **only** calibrated knobs — `top_k` / `max_context_tokens` — analyzed from retrieval quality at the Spike-Week Friday gate, then `lock_calibration`. **Type-Aware Decay `decay_d` is NOT calibrated** (frozen at design time, v5 D-0.3); Week-4 is a sanity check, not a tuning trigger. |

## For AI Agents

### Working In This Directory
- **All generative + embedding access must go through `llm_factory.py`.** Do not instantiate `openai.OpenAI()` elsewhere or read base URLs directly.
- Chat and embeddings are deliberately **two clients** (Ollama Cloud serves no embedder) — keep them separate.
- `EMBEDDING_DIM` must match the embedder and the FAISS index (D2). Changing it forces a FAISS rebuild and, post-lock, a full 144-run re-run.
- Calibration is a **one-time window** (Spike-Week Friday for top_k/tokens; Week-4 for decay_d). After lock, hyperparameters are frozen.

### Testing Requirements
- `tests/test_config.py`, `test_config_integration.py`, `test_llm_factory.py`. Example: `examples/config_usage.py`.
- Verify wiring with the live snippet in root `AGENTS.md` (expects a model reply + an embedding of length `EMBEDDING_DIM`).

### Common Patterns
- Precedence: `.env` env vars > `configs/base.yaml` > policy YAML override.

## Dependencies

### Internal
- Imported by virtually every `src/**` module that talks to a model or reads config.

### External
- `openai` SDK, `pyyaml`, `python-dotenv`, `pydantic`.

<!-- MANUAL: -->
