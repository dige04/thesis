# Literature Scan — Memory Pruning & Forgetting Policies for AI Coding Agents (2026-06-17)

> Source: Claude web Deep Research, run from the gap-targeted prompt. Citation-ready scan
> organized by the six priority areas, with novelty-threat flags and re-scoping advice.
>
> **HALLUCINATION-HYGIENE GATE (read before adding anything to `paper/refs.yml`):** every
> item the author cites must be re-checked against the live arXiv `/abs/` page (exact
> title, author list, ID). The items flagged in **Caveats** — FadeMem (2601.18642),
> Fofadiya & Tiwari (2604.02280), FluxMem (2602.14038) — and anything under
> "UNVERIFIED — DO NOT CITE" must NOT enter `refs.yml` without direct confirmation. The
> already-cited anchors (Xiong 2505.16067, Alqithami 2512.12856) are in `refs.yml` today.

## TL;DR
- **No verified peer-reviewed paper does exactly what this thesis does** — a
  retrieval-held-constant, six-policy forgetting comparison for *coding* agents on
  SWE-Bench-CL with a cost/footprint Pareto. The single closest threat is Alqithami 2025
  "Forgetful but Faithful" (arXiv:2512.12856), already in the bibliography but more
  dangerous than it appears, because it independently runs a six-forgetting-policy
  comparison swept across multiple memory budgets. The defensible wedge is *coding agents
  + retrieval-as-fixed-control*.
- Strongest new evidence to engage with: (1) Xiong et al.'s "experience-following
  property" driving error propagation, with selective addition+deletion yielding a 10%
  average absolute gain over naive memory growth (arXiv:2505.16067); (2) Chroma's "Context
  Rot" report (Hong, Troynikov & Huber, July 2025), 18 frontier models, non-uniform
  degradation as input grows; (3) the SWE-Bench Illusion audit (Liang, Garg & Zilouchian
  Moghaddam 2025, arXiv:2506.12286), bearing on SWE-Bench-CL construct validity.
- Add two methodological defenses with direct 2025-26 citations: a reasoning-token
  cost-accounting caveat (MiniMax M3 reasoning-token inflation) and a single-run
  stochasticity defense for re-evaluating a reasoning model.

## Key framing
The "controlled measurement" framing is defensible but the space is crowding fast. Field
pivoted toward storage-side forgetting/consolidation in 2025-26; ≥4 recent papers run
multi-policy or budget-swept forgetting comparisons — **all on conversational/QA
benchmarks (LoCoMo, PersonaMem, MultiWOZ, MSC), none on coding agents, none holding
retrieval constant as an isolated control.** That two-part distinction — coding +
retrieval-fixed — is the novelty to foreground in the Introduction, not bury in Related
Work. Second risk: SWE-Bench-CL is built on SWE-Bench Verified (OpenAI-deprecated as
contaminated); the within-system between-policy design is robust (contamination constant
across conditions) but the argument must be made explicitly.

---

## Area 1 — Storage-side memory management / selective retention / forgetting / consolidation

- **Forgetful but Faithful** — Saad Alqithami, 2025, arXiv:2512.12856. Six forgetting
  policies (FIFO, LRU, Priority Decay, Reflection-Summary, Random-Drop, Hybrid) + FiFA
  benchmark, multi-budget sweep; coherence/goal/recall/privacy/cost.
  **NOVELTY-THREAT.** Re-scope: (a) coding agents on SWE-Bench-CL vs FiFA's
  generative/privacy agents; (b) retrieval held constant as isolated IV, which FiFA does
  not do.
- **FadeMem: Biologically-Inspired Forgetting for Efficient Agent Memory** — Lei Wei et
  al., 2026, arXiv:2601.18642. Dual-layer adaptive exponential decay by relevance/freq/
  recency + LLM conflict resolution; ~45% storage reduction on MSC/LoCoMo/LTI-Bench.
  **Method-to-engage / partial NOVELTY-THREAT** — parallels Type-Aware Decay; differentiate
  (single system, conversational, retrieval not isolated). *Re-verify author list.*
- **Novel Memory Forgetting Techniques for Autonomous AI Agents** — Payal Fofadiya, Sunil
  Tiwari, 2026, arXiv:2604.02280. Adaptive budgeted forgetting (recency+frequency+
  semantic); non-inferior long-horizon F1, reduced false-memory on LoCoMo/MultiWOZ.
  **Discussion / partial NOVELTY-THREAT.** *Re-verify metadata (inconsistent date stamp).*
- **Choosing How to Remember (FluxMem)** — Mingfei Lu et al., 2026, arXiv:2602.14038.
  Beta-Mixture gate over memory structures (linear/graph/hierarchical), LRU + eligibility
  pruning; LoCoMo/PersonaMem. **Related Work.** *PDF renders empty — use HTML.*
- **LightMem** — Jizhan Fang et al., 2025, arXiv:2510.18866. Atkinson–Shiffrin 3-stage
  (sensory compression, topic-aware STM consolidation, sleep-time updates).
  **Related Work / Method-to-engage** (supports CLS-Consolidation).
- **ReasoningBank** — Siru Ouyang, Jun Yan et al., 2025, arXiv:2509.25140. Distills
  strategies from self-judged successes+failures; memory-aware test-time scaling; web + SE
  benchmarks vs No-Memory. **Related Work / Discussion** ("what to store" contrast).
- **Agent Workflow Memory** — Wang, Mao, Fried, Neubig, 2025, ICML 2025,
  OpenReview id=NTAhi2JEEE. Induces reusable workflows, selective injection. **Related Work.**
- **Structurally Aligned Subtask-Level Memory for SE Agents** — Kangning Shen et al., 2026,
  arXiv:2602.21611. Subtask-granularity memory; +4.7 pp mean Pass@1 (up to +6.8) on
  SWE-bench Verified, gains grow with steps. **NOVELTY-THREAT (scope) / Method-to-engage** —
  closest coding-agent memory paper; shows memory CAN recover performance → reconcile with
  the "non-inferior, diluted-benefit" story; differentiate (they vary retrieval
  granularity, not storage with retrieval fixed).
- **EXPEREPAIR** — Fangwen Mu et al., 2025, arXiv:2506.10484. Episodic+semantic memory;
  pass@1 60.3% (Lite)/74.6% (Verified). **Related Work** (coding dual-memory; type-aware).

## Area 2 — When to use memory / adaptive & gated retrieval
- **Xiong et al. 2025, arXiv:2505.16067** (already cited). "Experience-following property"
  → error propagation; "add-all" worse than no memory; selective add+delete = +10% abs.
  **Discussion anchor for "not every task needs memory."**
- **Adaptive-RAG** — Jeong et al., 2024, NAACL 2024, arXiv:2403.14403. Complexity-routed
  no/single/multi-step retrieval. **Related Work** (seminal "retrieve only when needed").
- **When to Retrieve / ADAPT-LLM** — Labruna, Campos, Azkune, 2024, arXiv:2404.19705.
  **Related Work** (memory task-dependent).
- **When Retrieval Succeeds and Fails** — 2025, arXiv:2510.09106. Retrieval can dilute
  attention. **Discussion** (dilution mechanism behind interdependence).

## Area 3 — Continual learning / context rot / distraction from accumulated history
- **Context Rot** — Hong, Troynikov & Huber, Jul 2025, Chroma report,
  research.trychroma.com/context-rot. 18 frontier models; non-uniform degradation as input
  grows; single distractor lowers accuracy. **Discussion (key motivation).** *Industry,
  not peer-reviewed; toolkit at chroma-core/context-rot.*
- **Catastrophic Forgetting in LLMs: A Comparative Analysis** — Naimul Haque, 2025,
  arXiv:2504.01241. Parametric (weight) forgetting. **Related Work** (demarcate: we study
  external-memory forgetting, not weight forgetting).

## Area 4 — Cost / efficiency tradeoffs & Pareto framing (incl. reasoning-token accounting)
- **Stop Wasting Your Tokens (SupervisorAgent)** — 2025, arXiv:2510.26585. ~29.68% token
  reduction Pareto on GAIA. **Related Work / Method-to-engage.**
- **ProST** — 2025, arXiv:2509.04508. Effectiveness-vs-FLOPs Pareto (cost proxy avoiding
  reasoning-token inflation). **Method-to-engage (cost-axis design).**
- **Decomposing Reasoning Efficiency** — 2026, arXiv:2602.09805. Correct answers per 1k
  output tokens; reasoning vs overthinking. **Method-to-engage** (M3 reasoning-token
  cost-accounting).
- **Token-Budget-Aware LLM Reasoning** — Tingxu Han et al., 2024/25, arXiv:2412.18547.
  **Discussion.**
- **Training Language Models to Reason Efficiently** — Arora & Zanette, 2025,
  arXiv:2502.04463. Accuracy-vs-reasoning-cost Pareto. **Discussion.**
- **G-Memory** — 2025, arXiv:2506.07398. Memory perf-vs-token-cost trade-off (10.32% gain).
  **Related Work (memory cost Pareto precedent).**
- **How persistent is the inference cost burden?** — Denain, 2025, Epoch AI.
  **Caveat (cost axis). Industry.**

## Area 5 — Harness / context engineering / production memory frameworks
- **Mem0** — Chhikara et al., 2025, ECAI 2025, arXiv:2504.19413. Extract/update
  ADD/UPDATE/DELETE/NOOP; ~10-approach head-to-head on LoCoMo; token cost. **Related Work.**
- **Zep / Graphiti** — Rasmussen et al., 2025, arXiv:2501.13956. Bitemporal KG memory,
  conflict resolution; "no-forgetting via versioning" counterpoint. **Related Work.**
- **Agentic Context Engineering** — 2025, arXiv:2510.04618. Context curation as locus of
  improvement. **Related Work** (bridge to "context engineering").
- **LangMem** — LangChain, 2025, github.com/langchain-ai/langmem. **Related Work
  (industry). Software, not peer-reviewed.**

## Area 6 — Methodology precedents (contamination, single-model, TOST, reproducibility)
- **The SWE-Bench Illusion** — Shanchao Liang, Spandan Garg, Roshanak Zilouchian
  Moghaddam, 2025, arXiv:2506.12286. Up to 76% buggy-file-path accuracy from issue text
  alone (53% on non-SWE-Bench repos) → memorization signal. **NOVELTY-THREAT (validity) /
  Method-to-engage.** Re-scope: within-system between-policy robust (contamination
  constant). *First author = Shanchao Liang.*
- **Why SWE-bench Verified no longer measures frontier coding capabilities** — OpenAI,
  2025. Contaminated + 18.8% over-broad tests. **Caveat. Industry.**
- **SWE-rebench** — 2025, arXiv:2505.20411. Decontaminated (temporal filtering).
  **Future Work / Method-to-engage** (robustness slice).
- **SWE-MERA** — 2025, arXiv:2507.11059. Dynamic contamination-resistant benchmark.
  **Future Work.**
- **Rigor, Reliability, Reproducibility (572 code benchmarks survey)** — 2025,
  arXiv:2501.10711. **Related Work (methodology).**
- **Can We Hide Machines in the Crowd?** — 2025, arXiv:2510.06658. TOST equivalence with
  pre-specified margin in NLP. **Method-to-engage (TOST precedent).**
- **TOSTER (R) — Intro to t_TOST** — Daniël Lakens, CRAN. **Method-to-engage** (TOST/SESOI
  tooling; cite Lakens' equivalence-testing tutorials for the ±0.03 CL-F1 SESOI rationale).
- **Phi-4-reasoning Technical Report** — Microsoft, 2025, arXiv:2504.21318. 50-run
  variance on AIME (30–70%); "single run can easily produce misleading conclusions."
  **Caveat / Method-to-engage** (single-re-eval stochasticity for M3).
- **Is one run enough? (biomedical reproducibility)** — 2026, JAMIA 33(6):1179. Majority
  vote over 3 runs adds stability estimate. **Caveat / Method-to-engage.**
- **Non-Determinism of "Deterministic" LLM Settings** — Berk Atil et al., 2024/25,
  arXiv:2408.04667. Temp-0 still non-deterministic. **Caveat.**
- **Defeating Nondeterminism in LLM Inference** — Thinking Machines Lab, 2025.
  Batch-invariance as nondeterminism source (relevant to free-router serving). **Caveat.
  Industry.**

---

## Top 5 must-cite
1. **Alqithami 2025 (2512.12856)** — closest novelty threat; differentiate early.
2. **Xiong et al. 2025 (2505.16067)** — best anchor that more memory can hurt; +10% abs from curation.
3. **Hong/Troynikov/Huber 2025 "Context Rot"** — mechanistic case for non-inferior forgetting.
4. **Liang/Garg/Zilouchian Moghaddam 2025 (2506.12286)** — pre-empt SWE-Bench-CL construct validity.
5. **Shen et al. 2026 (2602.21611)** — closest coding-agent memory result; reconcile with diluted-benefit story.

## Novelty risk assessment
No verified peer-reviewed work performs a retrieval-held-constant, multi-policy forgetting
comparison for coding agents with a Pareto/footprint framing. Alqithami (six-policy,
budget-swept) is on generative/privacy conversational agents and does not isolate
retrieval. FadeMem and Fofadiya & Tiwari are single systems on conversational benchmarks.
Shen et al. is the only close coding-agent study but varies retrieval granularity (not
storage with retrieval fixed) and frames memory as a *gain*, not non-inferiority. The
two-part wedge — coding agents on SWE-Bench-CL + retrieval as a fixed control isolating
storage policy — is defensible and currently unoccupied. (One informal Medium blog by
Markus Sandelin pre-stakes a "controlled isolation of memory in coding agents" claim;
**not** citable, but be aware.)

## Gaps the thesis uniquely hits
- **Retrieval-held-constant isolation of storage policy** — no verified competitor; cleanest
  causal-attribution design; strongest single selling point.
- **Interdependence quantification** — only ~⅓ of SWE-Bench-CL tasks structurally depend on
  predecessors (gold-patch file overlap); extends a limitation the SWE-Bench-CL authors
  flagged but didn't analyze.
- **Forgetting as non-inferiority, not recovery** — equivalence/TOST framing for memory
  policy is essentially absent (the field reports superiority of proposed methods).
- **Separating storage footprint from reasoning-token inference cost** — not present in the
  memory-Pareto literature; the right move given M3's reasoning-token inflation.

## Recommendations
1. **Pre-empt Alqithami in the Introduction** (one "what's different" paragraph: coding +
   retrieval-fixed). Threshold that would force a re-scope from "first controlled
   measurement" to "independent replication/extension": a peer-reviewed forgetting-policy
   comparison on a *coding* benchmark with retrieval fixed.
2. **Lead the interdependence section with Xiong et al. + Context Rot** — convert "benefit
   diluted" from a null into a mechanistically-grounded finding (error propagation +
   attention dilution explain *why* forgetting is non-inferior).
3. **Add a contamination paragraph** (SWE-Bench Illusion + OpenAI deprecation), then argue
   within-system between-policy robustness. If time permits, a SWE-rebench/SWE-MERA
   robustness slice as Future Work.
4. **Add a reasoning-token cost caveat** (Decomposing Reasoning Efficiency + Epoch AI);
   report storage footprint as a cost axis independent of completion tokens; consider a
   FLOPs-style proxy (ProST) to avoid reasoning-token inflation on the Pareto frontier.
5. **Defend single re-evaluation** (Phi-4-reasoning 50-run variance + JAMIA). Threshold: run
   ≥3 seeds on ≥1 sequence and report spread; if the between-policy effect is smaller than
   within-policy run-to-run variance, bound the stochasticity explicitly. *(Note: A7 already
   restored the full 3-seed × 144-run matrix — this defense is now satisfied, not aspirational.)*

## Caveats
- **Source quality:** Context Rot, OpenAI note, Epoch AI, Thinking Machines, LangMem, Mem0
  blog posts are industry / non-peer-reviewed — label as industry sources.
- **Verify before citing (hallucination hygiene):** re-check FadeMem (2601.18642),
  Fofadiya & Tiwari (2604.02280), FluxMem (2602.14038) against live arXiv pages. FluxMem
  PDF empty (use HTML); Fofadiya date stamp inconsistent.
- **Author-stated venues:** "ICLR 2026" (LightMem) and "ICML 2026" (FluxMem) are
  author/metadata claims — cite as "arXiv preprint" until confirmed on OpenReview.
- **UNVERIFIED — DO NOT CITE without direct confirmation:** "ENGRAM," "FSFM" (claimed
  2604.20300), "SWE-ContextBench" (surfaced only second-hand); Markus Sandelin Medium post
  (blog, not academic).
