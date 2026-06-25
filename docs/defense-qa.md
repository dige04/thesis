# Defense Q&A Sheet

> Highest-probability committee questions + grounded answers. Ordered by attack severity.
> Every answer uses only facts grounded in `AMENDMENTS.md` (A1–A7, D1–D6) and the gate-3
> findings. Model = MiniMax M3 (A7/D6); 3 seeds / 144 runs restored (A7).

**Q1. Why only one model? Isn't single-model a fatal external-validity threat?**
The thesis claim is *between-policy on a fixed model* (policy A vs B, model held
constant). Model is therefore a **fixed factor**, and holding it constant **maximizes
internal validity** by removing model as a confound. Generalization across models is a
*different research question*, addressed descriptively by the optional D-0.4 cross-model
probe, not by the primary matrix. We scope every claim to "within-system, between-policy."

**Q2. Then why not *block* on model — treat it as a stratifying factor?**
A properly blocked design (analyze *within* each model, never pool) would be clean — it
is **not** a confound, it just costs runs. We didn't, for three honest reasons: (a) it
answers generalization, outside the pre-registered between-policy claim; (b) each
model×policy×sequence cell would be underpowered at our seed budget; (c) it is a
separable follow-up study. Note we do **not** plead "no budget" — the free-unlimited
provider plus the 5-VPS fleet removed compute as a constraint.

**Q3. The executed model isn't even the pre-registered one (GPT-5.4).**
Declared deviation chain **D1: GPT-5.4 → Kimi → MiniMax M3**, every step dated and
documented in `AMENDMENTS.md`, held constant across all conditions × seeds. Absolute
solve rates are explicitly *not* comparable to GPT-5.4 or SWE-Bench leaderboards — we
never make that claim. The amendment trail is what protects the study from "you moved
the goalposts."

**Q4. Anchor-probe stability saturated at 1.000 — so there's no forgetting and the
question is moot?**
Two readings, both disclosed: either (a) genuinely no catastrophic forgetting in this
regime, or (b) the 5-anchor probe is **insensitive** to it (floor effect), compounded by
anchor re-evaluation being itself stochastic under a reasoning model at temperature 1.
This is precisely why our load-bearing efficiency claim rests on the **footprint axis**
(storage, directly measured), not on stability. We test reading (b) under A5.

**Q5. Does memory even help? Full ≈ No-Memory.**
That is itself a finding and we report it. On CL-F1, Full − No-Memory is **−0.097
(pytest), +0.018 (django)** — within noise. Structurally, only ~⅓ of tasks share files
with any predecessor (mean overlap **0.30**, **0.32** of tasks have any dependency), so a
sequence-level average benefit was always diluted. The thesis reframes from "forgetting
recovers performance" to "**forgetting is non-inferior to full memory at materially lower
footprint**" — and quantifying interdependence ("not every task needs memory," made
measurable) is itself the contribution.

**Q6. SWE-Bench is public — how do you rule out memorization/contamination?**
We can't fully; we bound the claim. M3's training cutoff is undocumented (0G router). We
restrict claims to within-model **contrasts**: any contamination is constant across
conditions, so it does not bias the between-policy comparison, only the (disclaimed)
absolute rates. We log model id, config hash, and dataset revision per run.

**Q7. A free rotating-key router (0G) + a reasoning model — is this reproducible?**
Reversible and logged: provider is `.env`-only; the 16-key rotation is for rate-limits,
not behavior; CoT is stripped deterministically before parsing/embedding (Invariant #4
payload stays CoT-free); JSON via tolerant extraction + Pydantic with logged failure
rate; embeddings are local and deterministic (`nomic-embed-text-v2-moe`, 768-d). The
token-cost axis is inflated by reasoning tokens — disclosed, and uniform across
conditions.

**Q8. Three seeds is thin for run-level variance, especially at temperature 1.**
Correct that temp 1 (endpoint constraint, A2) + a reasoning model means real run-to-run
stochasticity. We restored the full **3-seed × 144-run** matrix (A7) for exactly this,
and we report **seed-level spread separately from task-level bootstrap CIs** — they are
distinct variance sources and we never conflate them.

**Q9. CLS Consolidation — one of your six policies — never fired. Failed condition?**
A **negative result**, reported as one. On diverse same-repo coding memories, DBSCAN (≥3
memories at ≥0.70 cosine) never forms clusters, so CLS degenerates to its Type-Aware
fallback. We did **not** lower the similarity threshold to force it (frozen Invariant
#23; would produce garbage summaries). H3 (compressive forgetting) is therefore N/A on
this benchmark — a finding about *when* consolidation is even applicable.

**Q10. Seven amendments — isn't this p-hacking?**
Every amendment is dated, justified, held constant across conditions, and disclosed. Most
are mechanical fixes forced by deviations (cap 100→10 because sequences are short; temp
0→1 because the endpoint rejects 0) or construct corrections (H1b token-savings→footprint
because the mechanism cannot save tokens). **None were decided after seeing the affected
data.** That is the line between principled amendment and researcher-DoF abuse.
