# Deep Research Handoff — Citation Sweep for the Memory-Pruning Thesis

> **Purpose:** Paste this whole document into **claude.ai → Deep Research** (or any deep-research agent). It is self-contained — you do **not** need repo access to act on it. It tells you exactly what the thesis is, what literature it already cites, and what to return. A short list of repo files to *optionally attach* for extra fidelity is at the end.
>
> **Your job, in one line:** Produce the most complete, *verified*, *insightful* citation set I can use for this thesis — organized by where each paper plugs into my argument — and flag everything I'm currently missing.

---

## 0. How to use this handoff (instructions to the Deep Research agent)

1. Treat §1–§5 below as ground truth about the thesis. Do not redesign the study; I am not asking for methodological advice on the experiment itself.
2. Take the **30-paper seed list in §6** as my *current* bibliography. For each, **verify it exists** (correct authors/venue/year/arXiv-or-DOI), correct any wrong metadata, and extract the specific claim I can cite it for.
3. Then **expand**: find the papers I am *missing* in each topic area of §5, prioritizing (a) the standard/foundational work and (b) recent work (2024–2026) on agent memory, forgetting, continual learning for code, and context-window effects.
4. Return the **deliverables in §7** in the exact structure requested (annotated bibliography by thesis section + BibTeX + insights + gap list + contradiction list).
5. Be skeptical and concrete. For every paper, tell me **what it claims**, **how strong the evidence is**, and **which of my sections/hypotheses (H1–H5) it supports, complicates, or contradicts**. I value contradicting evidence as much as supporting evidence.

---

## 1. What the thesis is (ground truth)

**Title:** *Memory Pruning and Forgetting Policies for AI Coding Agents — Impact on Performance Across Sequential Tasks* (Master's thesis).

**One paragraph.** I run **six memory policies** (No Memory, Full Memory, Random Prune, Recency Prune, Type-Aware Decay, CLS Consolidation) across **all 8 official SWE-Bench-CL sequences × 3 seeds = 144 controlled runs** on a **single frozen LLM**, evaluate with the standard `eval_v3` SWE-Bench harness, and analyze with **sequence-level non-parametric statistics (Wilcoxon on N=8 sequence means + Holm correction, rank-biserial effect size, 5000-iteration BCa bootstrap)** plus an exploratory **task-level binomial GLMM**. The study tests whether **proactive forgetting matches or beats full-memory accumulation on the Pareto frontier of CL-F1 vs. operational cost**, and which *content-aware structure of forgetting* matters most.

**The contribution is methodological, not policy-set novelty.** The novelty claim is **controlled measurement**: standard benchmark + retrieval held *identical* across all six conditions (so the contrast is attributable to *storage* decisions, not retrieval) + No-Memory↔Full-Memory boundary baselines + pre-registered, effect-size-gated interpretation. I do **not** claim to invent new forgetting policies. Keep this framing in mind when judging relevance — I need citations that (a) ground each mechanism, (b) establish the gap, and (c) position me against the closest prior work.

---

## 2. Research question & hypotheses (what citations must support)

**Central question.** Under controlled retrieval, do proactive forgetting and consolidation policies achieve performance **non-inferior** to full-memory accumulation on sequential coding tasks while **materially reducing operational cost** — and which content-aware structure of forgetting matters most?

**Falsifiable hypotheses (each needs literature support and, ideally, contradicting evidence):**
- **H1.** Selective pruning achieves at least one of: (H1a) non-inferior CL-F1 vs. Full Memory (TOST equivalence, SESOI = ±0.03 CL-F1), and/or (H1b) ≥20% lower cost.
- **H2.** Semantically informed pruning (Type-Aware Decay) **outperforms random pruning** — *what* is forgotten matters beyond *how much*.
- **H3.** CLS Consolidation gives similar/marginally better raw performance than extractive pruning **but at higher cost** — failing the Pareto test against simpler policies.
- **H4 (Behavioral).** Full-memory accumulation induces measurable **analysis paralysis** (more tool calls, more syntax errors) that forgetting mitigates.
- **H5 (Boundary).** Pruning can **harm** when it removes rare but critical repo-specific memories — identifying when forgetting is unsafe.

---

## 3. The six policies & their mechanisms (each needs a literature anchor)

| Policy | Mechanism | Literature anchor I need solid |
|---|---|---|
| No Memory | Control: store/retrieve nothing | Baseline framing; "is memory worth it" evidence |
| Full Memory | Store everything, retrieve top-k under same budget | "add-all can be worse than no memory"; context-length-hurts evidence |
| Random Prune | Archive random at capacity (volume-only baseline) | Volume vs. selection isolation; "power of noise" in retrieval |
| Recency Prune | FIFO by recency | Recency/episodic-position effects |
| **Type-Aware Decay** | `score = base(type) × age^(−d(type)) × (1+retrieval_count)^0.5`, per-type decay | **Anderson & Schooler power-law decay**; Ebbinghaus/MemoryBank decay; failure-tier weighting; forgetting-as-regularization |
| **CLS Consolidation** | Every k=5 tasks, cluster old memories + LLM-summarize | **Complementary Learning Systems (McClelland 1995)**; abstractive consolidation; memory-summarization agents |

**Cross-cutting mechanisms that also need citations:**
- **Injection order = best item LAST** → *Lost in the Middle* (Liu et al. 2024) and positional sensitivity of retrieved context.
- **Reflection-to-typed-memory write step** → Reflexion (Shinn et al. 2023) as methodological precedent.
- **Static content taxonomy vs. dynamic linked memory** → contrast with A-MEM (Xu et al. 2025).
- **Estimation-over-NHST statistics** → Cumming (2014), Wasserstein et al. (2019).

---

## 4. Positioning vs. closest prior work (verify & extend this table)

The closest-by-name prior work is **Alqithami (2025)** — six forgetting policies, but on a *custom privacy-agent* benchmark (FiFA), different domain, no retrieval control, no boundary baselines, no pre-registration. I differentiate on: standard benchmark (SWE-Bench-CL), identical retrieval as confound control, No-Memory↔Full-Memory bracketing, per-sequence statistical unit, and pre-registered effect-size-gated framings.

**Please pressure-test this positioning:** find any *other* work that (a) tests multiple forgetting/memory policies for **coding** agents, (b) holds retrieval constant across conditions, or (c) studies memory growth → performance degradation in agents. If something undercuts my "first controlled Pareto map of forgetting policies for coding agents on a standard CL benchmark" claim, I need to know now.

---

## 5. Topic map — the literature areas a complete bibliography must cover

For **each** area: confirm my seed papers, add the standard works I'm missing, and add 2024–2026 work. Mark each suggestion with the area code.

- **A. Agent memory architectures for LLMs** — MemGPT, Generative Agents, A-MEM, MemoryBank, Letta, and newer agent-memory frameworks. *(Where my policies live.)*
- **B. Forgetting / pruning / consolidation (cognitive + ML)** — Anderson & Schooler power law, Ebbinghaus, forgetting-as-regularization (Richards & Frankland), active forgetting (Davis & Zhong), Complementary Learning Systems (McClelland et al. 1995). *(Grounds P4 & P5 formulas.)*
- **C. Context-window effects & retrieval position** — Lost in the Middle (Liu et al. 2024), Power of Noise (Cuconasu et al. 2024), "context length hurts" (Du et al. 2025), episodic-memory position (Pink et al. 2025), observation masking (Lindenbauer et al. 2025). *(Grounds injection order + "more context can hurt".)*
- **D. Memory/long-horizon benchmarks for agents & code** — SWE-Bench-CL (primary, Joshi et al. 2025), SWE-ContextBench, MEMTRACK, MemBench (cost), subtask-level memory (Shen et al. 2026), Confucius Code Agent (Wong et al. 2025). *(Benchmark landscape + cost framing.)*
- **E. Continual learning metrics & lifelong-learning framing** — Plasticity/Stability/CL-F1, forward/backward transfer, lifelong-learning roadmap (Zheng et al. 2025), and the CL-metrics literature these derive from. *(Grounds my metric choices.)*
- **F. Reflection / self-improvement / memory-write** — Reflexion (Shinn et al. 2023) and successors that turn experience into stored memory. *(Grounds §9 reflection step.)*
- **G. Statistics / methodology** — estimation-over-testing (Cumming 2014), ASA statement on p-values (Wasserstein et al. 2019), TOST equivalence testing, BCa bootstrap, rank-biserial, GLMM for binary clustered data. *(Grounds my analysis plan — find the canonical method citations I should be using for TOST, BCa, and GLMM.)*
- **H. Coding-agent foundations (context only)** — SWE-Bench / SWE-Bench Verified, ReAct, LangGraph-style agents. *(Background; light coverage.)*
- **I. Cost / efficiency of agent memory** — Mem0/Zep cost-explosion analyses (Fastpaca blog series), MemBench. *(Grounds the cost axis of the Pareto study; note: some of these are blog posts — please find peer-reviewed or arXiv equivalents where they exist.)*

---

## 6. Current seed bibliography (verify, correct, and extract the citable claim for each)

These are the 30 references currently in the thesis (from `THESIS_FINAL_v5.md §26`). **For each: confirm metadata, give the precise claim I can cite it for, and note if a stronger/more-canonical source exists.** Bold = load-bearing.

| # | Reference (as I have it) | Role I assigned | Area |
|---|---|---|---|
| 1 | Anderson & Schooler (1991) | Power-law decay — P4 formula grounding | B |
| 2 | Richards & Frankland (2017), *Neuron* | Forgetting as regularization | B |
| 3 | **McClelland, McNaughton & O'Reilly (1995), *Psych Review*** | CLS theory — grounds P5 | B |
| 4 | Davis & Zhong (2017), *Neuron* | Active forgetting | B |
| 5 | **Xiong et al. (2025), arXiv:2505.16067** | Add-all worse than no memory | A/C |
| 6 | Lindenbauer et al. (2025), NeurIPS DL4C, arXiv:2508.21433 | Observation masking (in-task) | C |
| 7 | Zhu et al. (2026), arXiv:2602.08316 | SWE-ContextBench | D |
| 8 | **Joshi et al. (2025), arXiv:2507.00014** | **SWE-Bench-CL (PRIMARY benchmark)** | D |
| 9 | Deshpande et al. (2025), NeurIPS, arXiv:2510.01353 | MEMTRACK | D |
| 10 | Du et al. (2025), EMNLP, arXiv:2510.05381 | Context length hurts | C |
| 11 | **Liu et al. (2024), TACL** | **Lost in the Middle — injection order** | C |
| 12 | Cuconasu et al. (2024), SIGIR, arXiv:2401.14887 | Power of Noise | C |
| 13 | **Alqithami (2025), arXiv:2512.12856** | Closest-by-name: 6 forgetting policies on FiFA (privacy agents) | A |
| 14 | Shen et al. (2026), arXiv:2602.21611 | Subtask-level memory | D |
| 15 | Sun et al. (2022), ICLR 2023 | Info-theoretic selection | B/A |
| 16 | Pink et al. (2025), arXiv:2502.06975 | Episodic memory position | C |
| 17 | Letta (2025), blog | Filesystem beats memory | A/I |
| 18 | Wong et al. (2025), arXiv:2512.10398 | Confucius Code Agent | D |
| 19 | Fastpaca (2025), blog | Mem0/Zep cost explosion | I |
| 20 | Fastpaca (2026), blog | Memory taxonomy | I |
| 21 | Fastpaca (2025), blog | Failure-mode design — type weights (grounds P4 type weights) | B/I |
| 22 | MemBench (2025), arXiv:2506.21605 | Cost benchmark | D/I |
| 23 | **Packer et al. (2024), ICLR** | MemGPT | A |
| 24 | **Park et al. (2023), UIST** | Generative Agents | A |
| 25 | Zheng et al. (2025), IEEE TPAMI | Lifelong-learning roadmap | E |
| 26 | **Cumming (2014), *Psychological Science*** | Estimation-based inference | G |
| 27 | **Wasserstein et al. (2019), *The American Statistician*** | ASA statement on p-values | G |
| 28 | Zhong, Guo, Gao, Ye & Wang (2024), AAAI | MemoryBank (Ebbinghaus decay) — closest analog to P4 | A/B |
| 29 | Xu, Liang, Yan, Li, Liu, Yan, Jin & Wen (2025), arXiv:2502.12110 | A-MEM (dynamic linked memory) — contrast w/ my static taxonomy | A |
| 30 | Shinn, Cassano, Berman, Gopinath, Narasimhan & Yao (2023), NeurIPS | Reflexion — reflection-as-memory precedent | F |

---

## 7. Deliverables — return these, in this structure

**(1) Verified + corrected seed table.** The 30 above with: confirmed citation, corrected metadata where wrong, a 1–2 sentence *precise* claim I can cite, and a flag if a more canonical source exists. Replace blog posts (17, 19, 20, 21) with peer-reviewed/arXiv equivalents where they exist; if not, say so.

**(2) Annotated bibliography of NEW papers, grouped by thesis section**, using these buckets (map to areas A–I):
   - *Related Work — Agent Memory* (A)
   - *Related Work — Forgetting/Consolidation, cognitive + ML* (B)
   - *Related Work — Context-window & retrieval-position effects* (C)
   - *Benchmarks & metrics* (D, E)
   - *Reflection / memory-write* (F)
   - *Methods/Statistics canonical citations* (G) — specifically: a citation for **TOST equivalence testing** (e.g., Lakens), **BCa bootstrap** (Efron), **rank-biserial correlation**, and **GLMM for binomial clustered data**.

   For each new paper: full citation, arXiv/DOI link, venue + year, a 2–4 sentence insight (what it shows + method + strength of evidence), **which hypothesis/section it serves**, and whether it **supports / complicates / contradicts** my framing.

**(3) BibTeX block** for every paper (seed + new) so I can drop it straight into the thesis.

**(4) Gap list.** Where is my bibliography thin or missing a standard reference a committee would expect? Be specific (e.g., "no citation for the original Plasticity/Stability CL-metric definitions", "no canonical TOST reference").

**(5) Contradiction / risk list.** Papers whose findings *undercut* a hypothesis or my novelty claim — especially: any prior work doing controlled multi-policy memory comparison for coding agents (would weaken H-framing and §4 positioning), or evidence that "more memory always helps" on code tasks (would threaten H1/H4).

**(6) Recency scan.** 2024–2026 work on agent memory / forgetting / continual learning for code that I have not cited. Prioritize peer-reviewed and well-cited arXiv.

**Quality bar:** verify every citation actually exists (no hallucinated papers, no invented arXiv IDs). If you cannot verify a paper, mark it `UNVERIFIED` rather than asserting it. Prefer primary sources over secondary summaries.

---

## 8. Repo files to attach for extra fidelity (optional)

Everything needed is embedded above, but if claude.ai lets you attach files, these give the agent the richest grounding (in priority order):

| File | Why attach it | What's in it |
|---|---|---|
| `THESIS_FINAL_v5.md` | **The single source of truth.** | Full spec: §1 RQ/hypotheses/positioning, §8 the six policies w/ formulas, §14 metrics, §15 statistics, **§26 the reference table**, §20 threats to validity. |
| `CLAUDE.md` | Frozen decisions + the Ollama-Cloud runtime deviations (D1–D5) | The 16 frozen invariants and what's locked vs. calibrated; the model/embedder/cost-metric/host deviations (affects which *absolute* numbers are comparable to leaderboards — relevant if you cite SWE-Bench scores). |
| `AGENTS.md` (root) + per-dir `AGENTS.md` | Map of how the design is realized in code | Confirms which mechanism lives where (e.g., `src/memory/policies/type_aware_decay.py` for the Anderson-Schooler formula, `src/agents/prompts.py` for best-item-LAST injection). |
| `.kiro/specs/memory-pruning-research-system/{requirements,design}.md` | Formal requirements/design derived from v5 | Useful if you want the requirement-numbered framing. |

> If attaching, tell the agent: *"`THESIS_FINAL_v5.md` is authoritative; `§26` is my current reference list — verify and expand it."*

---

## 9. Out of scope (don't suggest these)

- New experimental conditions (a 7th/8th policy), changes to the formulas, or swapping statistical tests — the design is locked.
- Methodological redesign of the study. I want **citations and insights**, not a new plan.
- Papers behind the "should I add X?" creep: only surface a paper if it grounds a mechanism, establishes the gap, supports/contradicts a hypothesis, or is a canonical method reference.
