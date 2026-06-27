# A5 Decision Memo — anchor-probe scope

> Operationalizes A5 (pending in `AMENDMENTS.md`). Reframes the open decision from a
> compute-budget question to a measurement-validity question, and proposes a cheap test
> that lets the data choose between A5 options (a) and (c).

## Status & reframe

A5 is *pending* and currently framed as a **budget** question ("is the full
~1,900-re-evaluation anchor-probe worth ~days of compute for a dimension that was
uninformative in the pilot?"). **Reframe it as a validity question:** *is the stability
instrument capable of discriminating between conditions at all in this regime?* Budget is
the wrong axis — with the free-unlimited provider, compute is cheap; the real risk is
spending it on a metric that is structurally blind.

## Why it might be blind (grounded)

Stability = 1.000 and the E7 interdependence finding are the **same phenomenon**. If only
~⅓ of tasks share files with predecessors (mean overlap 0.30; 0.32 of tasks have any
dependency), and the five gate-3 anchors were drawn from the file-disjoint ⅔, then memory
was never load-bearing for them and stability *cannot* move regardless of policy. A
saturated metric on a non-interdependent sample is uninformative, not reassuring.

## Proposed discrimination test (cheap — tens of re-evals, not ~1,900)

1. Use the two gate-3 sequences (django, pytest) plus one high-interdependence sequence
   (e.g. sphinx/xarray, overlap ≈ 0.50).
2. **Target anchors at interdependent tasks** — select anchors whose gold-patch files
   overlap a *later* task, using `structural_interdependence` / `parse_patch_files` from
   `src/analysis/interdependence.py`. These are the only tasks where forgetting *could*
   show up.
3. Run the anchor-probe for the **most-separated contrast**: Full Memory vs. an aggressive
   pruner (Random or Recency at cap = 10).
4. Because M3 re-evaluation is stochastic (reasoning, temp 1), run each targeted anchor
   ≥3× and report the spread rather than a single binary.

## Decision rule

- If stability **discriminates** (Full detectably > aggressive-prune) on the targeted,
  interdependent anchors → instrument works → proceed with the full anchor-probe
  (**A5 option a**).
- If stability **stays 1.000** even on interdependent anchors under the most-separated
  contrast → instrument is blind in this regime → **demote anchor-probe stability**,
  report CL-F1 as plasticity-driven (**A5 option c**), and move the efficiency claim
  entirely to the footprint axis — disclosed as the measurement-validity threat in
  Threats to Validity.

## Recommendation

Run **option (b)** first; let it choose between (a) and (c) with data, *before* committing
the matrix's anchor-probe budget (as A5 itself requires).

## Constructibility pre-flight result (2026-06-22 — FREE, no re-evals)

Before spending any compute, ran a local check: for an (anchor A, probe p) cell to be able
to discriminate Full vs aggressive-prune, there must exist a record R that is (1) relevant to
A (R.files_touched overlaps A's gold-patch files), (2) ACTIVE in Full as-of-p, and (3) EVICTED
in the prune run as-of-p. If no such cell exists, the probe is blind *by construction* → (c)
for free. Computed from gold patches (`parse_patch_files`) + the flash runs' `memory.db`
as-of-p archived logic (copied from `restore_memory_state`).

**Result for pytest (highest memory_lift, +0.21):** the probe is **constructible** — NOT
blind by construction.
- **112** discriminating cells vs `recency_prune` (cap=10); **112** vs `random_prune`.
- **13** of them land on the §14.2 anchors `[2,6,10,14,18]` × probes `[5,10,15,19]`.
- Two kinds: **OWN-record** cells (Full keeps the anchor's own solution memory; prune evicted
  it) and genuine **predecessor** cells (the interdependent intent): task5←task0 (`capture.py`),
  task9←task6 (`pathlib.py`), task12←task4 (`skipping.py`), task14←task2 (`python.py`),
  task17←task2, task15←task13 (`logging.py`).
- pytest structural interdependence: mean_prior_overlap=0.361, frac_tasks_with_dependency=0.389.

**Implication:** the pre-flight did NOT hand us a free (c) — a discriminating contrast EXISTS
structurally. So the live re-eval (option b) is genuinely needed to decide (a) vs (c): does
retaining those relevant memories actually change Full's solve outcome on those cells, or does
stability stay saturated even where it structurally could move? Pre-flight script:
`scratchpad/preflight_pytest.py`.

### Retrieval-aware refinement (2026-06-22 — still free, embeddings only)

The file-overlap pre-flight OVERCOUNTS: retrieval is pure cosine over [issue] embeddings, NOT
file overlap. A smoke test exposed this — anchor14@p15's file-overlapping predecessor (seq=2,
`python.py`) is RETAINED in full but never enters the cosine top-5, so that cell can't
discriminate (for "retrieval missed P", not "metric blind"). Re-scanned every cell comparing
full's vs recency's actual RETRIEVED set (`scripts/preflight_retrieval_aware.py`, run on sfo-4):

**49 cells have a genuinely different retrieved set** → the probe is **NOT retrieval-blind**.
The cleanest are **own-record-forgotten cells at probe 19**: by end-of-sequence, recency (cap=10)
has evicted the early anchors' OWN solution memory entirely while full still retrieves it
(e.g. anchor0@p19: full `[0,0,0,11,16]` vs recency `[12,14,17,17,18]` — recency has zero trace
of task 0). This is the sharpest stability/forgetting test possible in this dataset.

**Live probe LAUNCHED (sfo-4, deepseek-v4-flash):**
`scripts/run_anchor_probe_discrimination.py` — 7 cells (anchors 0–4 @p19 own-forgotten + 2
predecessor cells) × {full_memory, recency_prune cap=10} × 3 reps = 42 re-evals. Records
resolved 0/1 + target_in_topk per re-eval; writes `runs/anchor_probe_discrimination{.jsonl,_summary.json}`.
Decision rule unchanged: full's anchor accuracy detectably > recency's → option (a); both
equal (stability saturated even where retrieval differs) → option (c).

## DECISION (2026-06-22): option (c) WITH positive construct-validity evidence

42/42 re-evals clean (0 null/error). Results on the 5 own-record-forgotten cells (full retrieves
the anchor's OWN solution memory; recency cap=10 evicted it — confirmed target_in_topk full=True,
recency=False on all 5):

| cell | full | recency |
|---|---|---|
| a0@p19 | 3/3 | 2/3 |
| a1@p19 | 3/3 | **3/3** |
| a2@p19 | 3/3 | **0/3** |
| a3@p19 | 3/3 | **3/3** |
| a4@p19 | 2/3 | 1/3 |
| total | **14/15 (0.93)** | **9/15 (0.60)** |

Predecessor (forward-transfer) cells a9←seq4, a12←seq4: **0/0 in BOTH conditions** (floor — uninformative).

**Interpretation (the honest reading):**
1. The stability instrument is **NOT measurement-blind.** Existence proof: a2 is 3/3 (full) vs
   0/3 (recency), clean, with the mechanism confirmed (full retrieved seq2, recency had it evicted).
   Forgetting a *retained-and-retrieved* solution can cost a solve. (No p-value: these cells were
   SELECTED to maximize discrimination → significance testing is invalid by construction; reps are
   independent draws, not matched pairs. 14/15 vs 9/15 is descriptive texture, not inference.)
2. The signal is **backward stability only** (re-solving a task whose OWN solution was retained).
   The forward / cross-task interdependence cells were floor in both conditions → this probe gives
   **NO support for "earlier-task memory helps later tasks" (E7)**. Do not let the write-up slide
   from "memory aids backward retention" into "supports interdependence."
3. Causal phrasing: recency did not have *no* memory — it retrieved *different* (later) records. So
   a2 = "lost the helpful memo" OR "gained a distracting one." State narrowly.

**Decision = A5 option (c)-with-positive-evidence:**
- Report **CL-F1 = resolve-rate (proxy)** as the primary CL metric (unchanged headline: no policy
  beats full_memory, 144/144).
- Present this targeted test as a **construct-validity sub-study**: the stability instrument works
  but the natural SWE-Bench-CL regime rarely exercises it (most tasks solvable without memory, or
  the relevant memory isn't cosine-retrieved → the saturated stability≈1.000 of gate-3).
- Move the efficiency claim to the **footprint axis** (A4/H1b two-axis Pareto). Disclose the
  measurement-validity threat in Threats to Validity.
- **Full ~1,900-re-eval anchor-probe DECLINED**: (a) the fleet was deleted on user instruction; (b)
  it runs the FIXED §14.2 anchors, which are NOT selected for retrieval-difference → it would
  dilute this conditional signal across mostly floor/ceiling/identical-retrieval cells and almost
  certainly reproduce the saturated ≈1.000 aggregate at great cost. If a committee later demands
  it, rebuild the fleet. Data: `results/anchor_probe_discrimination/`.
