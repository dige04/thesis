<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# configs/policies

## Purpose
Per-policy YAML overrides merged on top of `configs/base.yaml`. Each file contains **only** the parameters that distinguish its policy — retrieval stays identical across all conditions, so these files never touch retrieval scoring.

## Key Files
| File | Description |
|------|-------------|
| `type_aware_decay.yaml` | Type-Aware Decay (P4) parameters: per-type `decay_d` and base values for the Anderson-Schooler formula. **Frozen at design time** (v5 D-0.3, §8 P4) — not calibrated; Week-4 is a sanity check only. |

## For AI Agents

### Working In This Directory
- Overrides are storage-side only. Never add retrieval bonuses/penalties here (invariant #5).
- P4's per-type `decay_d` is the one calibrated knob; once locked, changing it forces a full re-run.
- No-Memory / Full-Memory / Random / Recency / CLS either need no override or read their locked params from `base.yaml`; add a file here only when a policy needs a distinct override.

## Dependencies

### Internal
- Merged by `src/config/loader.py`; consumed by `src/memory/policies/type_aware_decay.py`.

<!-- MANUAL: -->
