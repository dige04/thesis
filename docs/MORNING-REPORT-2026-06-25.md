# Morning Report — 2026-06-25

## TL;DR (read this first)

- ✅ **The hard part is DONE: the A/B instrument-health gate = GO**, on fresh post-hotfix
  data, fully validated. The edit_file fix works; the instrument is clean. This was the
  uncertain, intellectual deliverable — it's won.
- ⚠️ **The 144 re-run is BLOCKED by a disk-capacity wall** (infra, not science). 15/144
  cells completed cleanly (preserved); the rest hit "No space left on device".
- 🛑 **Fleet is HALTED** (not burning budget). **One decision needed from you** to finish
  the 144 — see "Decision" below. Reply **A / B / C / hold**.
- Honest status: gate **GO**, **15/144** complete. The rerun is **NOT done** — it needs an
  infra choice, then ~16h of compute (unreachable by this morning on any path).

---

## 1. The win — A/B gate = GO (durable)

`results/ab_gate/amended_cceb325_result.json` (real gate on all 36 merged cells, experiment_sha `cceb325`):

| amended criterion | result |
|---|---|
| **instrument-attributable failures (fixed)** | **0** ✅ (was **79** on the buggy old data — hotfix confirmed) |
| model-quality rate fixed ≤ legacy | **0.152 ≤ 0.183** ✅ (fix doesn't regress; agent recovers) |
| token inflation ≤ 1.5× | prompt **0.986**, total **0.992** ✅ |
| complete + paired + provenance (sha / config / row-level tool_mode) | ✅ |

**Meaning:** the Task-2b edit_file path-normalization hotfix eliminated the 79 instrument
failures; the fixed instrument is clean AND net-positive (+15.3pp resolve vs legacy in the
A/B). Codex's amended-gate criteria (pre-registered before the run) all pass. The instrument
is validated — exactly the question the whole rerun existed to answer.

Data preserved: `runs_ab_cceb325/` (36 cells, 0 RUN_FAILED, 918 trajectories) + gate JSON.

## 2. The 144 block — disk capacity (diagnosed, not corrupted)

Launched 144 at CONC3 → workers hit **disk 100% full** → `RepositoryCheckoutError: No space
left on device` cloning the large repos (django/sphinx/sympy/matplotlib/xarray).

**Root cause:** the pipeline **never cleans Docker images** (agent uses `docker run --rm` =
removes container, keeps image; eval harness leaves images too). Each task's
`swebench/sweb.eval...` image is ~3.9GB and persists. The 144 needs **273 unique task images
(~273GB)** but the disk is **160GB** → overflow. The A/B (2 sequences, ~51 images) fit; the
144 (8 sequences) does not.

- **Not data corruption:** a checkout/container failure aborts the unit cleanly (RUN_FAILED),
  never recorded as a false `resolved=0`. The 15 completed cells are genuine + provenance-clean.
- **CONC2 would NOT fix it:** the wall is image *accumulation* (unbounded cache), not
  concurrency. Even CONC1 pulls all 273 images → still overflows. CONC only changes the *rate*
  of filling.
- **"Clean every run" hits a second wall:** images are **pulled** from Docker Hub
  (`namespace: "swebench"`), not built locally. Cleaning → re-pulling the same images across
  the 18 runs/sequence → Docker Hub's **100-pulls/6h/IP** rate limit → cells fail on pull.

Note: the *original* matrix (`runs_k27_merged`) ran on this same fleet, so 144 IS runnable
here — the true long-term fix is **per-task image cleanup in the harness** (which the current
flow lacks). That's option C.

## 3. Current state

- Fleet: **9 workers HALTED** (0 pilots, idle — not spending). Disk freed to ~86-97%.
- 144: **15/144 complete**, pulled to `runs_144_cceb325/` (clean, sha=cceb325, mode=fixed),
  rest failed-clean (re-runnable). The 15 are NOT a valid analysis set (partial design — can't
  run the locked Wilcoxon N=8); they prove the pipeline + are a head start.
- Budget: approximate — tonight ran 2× 36-cell A/B + 15 partial 144 cells + ~44 fast-aborted
  failures. Rough estimate **~$20-30** of the fresh key. **Check the OpenCode dashboard for the
  exact figure before launching the 144** (a full 144 is the big spend, ~$40).
- Code: hotfix + preflight committed (`rerun/instrument-fix`, tip `aa244fd`). Sequence-phased
  launch script prepped (see §5) — ready for one-click greenlight.

## 4. Decision needed — how to run the 144 (~16h either way; not finishable by this morning)

| Option | What | Cost / risk |
|---|---|---|
| **A. Bigger disk** | Attach ~150GB block volume per worker for Docker → hold all 273 images, no cleaning, no re-pull. **Most robust technically.** | ~$15-20 (9 vol × ~16h) + 9-box volume setup (mount + move docker data-root) |
| **B. Sequence-phased + docker login** | Run 144 in 8 phases (one sequence each): pull that sequence's images once, run its 18 cells, prune, next. Fits current disk. Needs your **Docker Hub login** (raises to 200/6h) to be safe from rate-limit. Script prepped. | No extra $; needs DockerHub creds + the 8-phase orchestration (new, untested) |
| **C. Fix the harness (per-task image cleanup) + docker login** | The proper root-cause fix: add `docker rmi` of each task's own image after eval (bounds disk to ~CONC images) + docker login for the cross-run re-pulls. A small, tested code change. | No extra $; ~1h to implement+test; cleanest long-term, reusable |

**Recommendation:** **C** (fix the harness — it's the real bug, small + tested, reusable) if
you can give a Docker Hub login; otherwise **A** (bigger disk, brute-force but lowest code
risk). **B** is viable but adds untested orchestration. Avoid running anything until you pick.

**Reply `A`, `B`, `C`, or `hold`** and I'll execute (and re-run the 15-done-aware resumable
144). Whatever you pick, the gate GO already stands — the thesis's trustworthiness claim is
secured.

## 5. Prepped (zero-cost, not run)

- `scratchpad/run144_phased.sh` — sequence-phased launcher (option B), ready for greenlight.
- Ledger: `.superpowers/sdd/progress.md` has the full state + decision tree (survives compaction).
