<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# configs

## Purpose
The complete experiment configuration (v5 §13). `base.yaml` holds the locked defaults shared by all runs; per-policy files in `policies/` add only the overrides that policy needs. Env vars from `.env` override YAML at load time (via `src/config/loader.py` + `llm_factory.py`), which is how the Ollama Cloud deviations D1–D4 are applied without editing locked values.

## Key Files
| File | Description |
|------|-------------|
| `base.yaml` | Locked defaults: the 6 conditions, 3 seeds, model names (D1), embedder + dim (D2), `cost_metric_mode` (D3), `top_k`/`max_context_tokens` (calibration defaults 5 / 2000), memory budget, agent limits, logging paths. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `policies/` | Per-policy YAML overrides (see `policies/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- `base.yaml` encodes frozen decisions (6 conditions, 3 seeds, locked formula params). **Changing a frozen value requires asking the user** and, post-calibration-lock, forces a full 144-run re-run.
- Prefer setting runtime/provider values in `.env` (env overrides YAML) rather than editing `base.yaml`, so the repo stays runnable on OpenAI/GPT-5.4 by `.env` edits alone.
- `top_k` and `max_context_tokens` are TBD-until-calibration; change **once** at the Friday gate, then lock. Type-Aware Decay `decay_d` is **not** calibrated — frozen at design time (v5 D-0.3).

### Testing Requirements
- `tests/test_config.py`, `test_config_integration.py`. Example: `examples/config_usage.py`.

## Dependencies

### Internal
- Consumed by `src/config/loader.py`.

### External
- YAML.

<!-- MANUAL: -->
