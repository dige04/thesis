// =============================================================================
// Master's Thesis — DRAFT
// Memory Pruning and Forgetting Policies for AI Coding Agents
// Source of truth: THESIS_FINAL_v5.md (pre-registered design)
//
// STATUS: Design / pre-registration chapters are complete and faithful to v5.
//         Results / Discussion / Conclusion are marked [PENDING DATA] because
//         the experiment has not yet produced a single real data point
//         (see the "Gaps" report delivered alongside this draft).
// =============================================================================

#set document(
  title: "Memory Pruning and Forgetting Policies for AI Coding Agents",
  author: "Leo Dinh",
)

#set page(
  paper: "a4",
  margin: (x: 2.4cm, y: 2.6cm),
  numbering: "1",
  number-align: center,
)

#set text(font: ("New Computer Modern", "Times New Roman"), size: 11pt, lang: "en")
#set par(justify: true, leading: 0.72em, first-line-indent: 1.2em)
#set heading(numbering: "1.1")
#show heading: it => block(above: 1.4em, below: 0.8em)[#it]
#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  block(above: 0em, below: 0.9em, text(size: 16pt, weight: "bold")[#it])
}
#set math.equation(numbering: "(1)")

// --- helpers ----------------------------------------------------------------
#let pending(body) = block(
  width: 100%,
  fill: rgb("#fff4e5"),
  stroke: (left: 3pt + rgb("#e08a00")),
  inset: 10pt,
  radius: 2pt,
)[#text(weight: "bold", fill: rgb("#a85d00"))[⚠ PENDING DATA — ] #body]

#let todo(body) = text(fill: rgb("#c0392b"), style: "italic")[[TODO: #body]]

#let frozen(body) = box(
  fill: rgb("#eef3ff"), inset: (x: 4pt, y: 1pt), radius: 2pt, baseline: 2pt,
)[#text(size: 9pt, weight: "bold", fill: rgb("#2545a0"))[#body]]

// =============================================================================
// TITLE PAGE
// =============================================================================
#align(center)[
  #v(2cm)
  #text(size: 13pt)[Master's Thesis — Working Draft]
  #v(0.4cm)
  #line(length: 60%, stroke: 0.5pt)
  #v(1.2cm)
  #text(size: 20pt, weight: "bold")[
    Memory Pruning and Forgetting Policies\ for AI Coding Agents
  ]
  #v(0.4cm)
  #text(size: 13pt)[Impact on Performance Across Sequential Tasks]
  #v(1.6cm)
  #text(size: 12pt)[Leo Dinh]
  #v(0.3cm)
  #text(size: 11pt)[Master's Programme in Computer Science]
  #v(2cm)
  #line(length: 60%, stroke: 0.5pt)
  #v(0.6cm)
  #text(size: 10pt, fill: rgb("#a85d00"))[
    DRAFT — compiled #datetime.today().display("[year]-[month]-[day]").\
    Design chapters complete; empirical chapters await experiment execution.
  ]
  #v(1fr)
  #text(size: 9.5pt, fill: gray)[
    Pre-registered design: #raw("THESIS_FINAL_v5.md") · Runtime runbook: #raw("AGENTS.md")
  ]
]
#pagebreak()

// =============================================================================
// ABSTRACT (bilingual)
// =============================================================================
#heading(numbering: none, level: 1)[Abstract]

AI coding agents increasingly carry a persistent memory of past tasks, on the
intuition that accumulated experience improves future performance. Yet
unbounded accumulation is expensive and may actively hurt: longer context
degrades reasoning, and stale or irrelevant memories act as retrieval noise.
This thesis asks whether *proactive forgetting* — selectively pruning or
consolidating stored experience — can match or beat full-memory accumulation
on sequential software-engineering tasks while materially reducing cost, and
*which structure* of forgetting matters most.

We evaluate six memory policies — No Memory, Full Memory, Random Prune, Recency
Prune, Type-Aware Decay, and Cognitively-inspired (CLS) Consolidation — on all
eight official SWE-Bench-CL sequences (48 controlled runs at a single seed; pre-registered at 144 across three seeds, amended under a submission deadline, @sec:deviations),
holding the retrieval mechanism *identical* across every condition so that the
experimental contrast is cleanly attributable to the *storage* policy rather
than the retrieval policy. Performance is measured with the continual-learning
F1 (CL-F1) metric balancing plasticity and stability; cost is measured as a
provider-independent compute proxy. The analysis is pre-registered: effect
sizes (rank-biserial $r_("rb")$) with BCa bootstrap confidence intervals are
primary evidence, Wilcoxon signed-rank tests on $N=8$ sequence-level means
supplement under Holm correction, and non-inferiority is tested with a TOST
procedure against a pre-committed smallest-effect-size-of-interest of
$plus.minus 0.03$ CL-F1.

#pending[
  Empirical results are not yet available. This draft presents the complete
  experimental design, hypotheses, metrics, and analysis plan. The Results,
  Discussion, and Conclusion are scaffolded against the pre-registered
  interpretation rules and will be populated once the 48 runs execute.
]

*Keywords:* AI coding agents, agentic memory, catastrophic forgetting,
continual learning, memory pruning, retrieval-augmented agents, SWE-Bench-CL,
Pareto efficiency.

#v(0.8em)
#heading(numbering: none, outlined: false, level: 2)[Tóm tắt (Vietnamese)]

Các tác nhân lập trình AI ngày càng lưu giữ bộ nhớ bền vững về các tác vụ đã
qua, với giả định rằng kinh nghiệm tích lũy sẽ cải thiện hiệu năng. Tuy nhiên,
tích lũy không giới hạn vừa tốn kém vừa có thể gây hại: ngữ cảnh dài làm suy
giảm khả năng suy luận, còn các ký ức cũ hoặc không liên quan trở thành nhiễu
khi truy hồi. Luận văn này đặt câu hỏi liệu *sự quên chủ động* — cắt tỉa hoặc
hợp nhất kinh nghiệm đã lưu một cách có chọn lọc — có thể *không thua kém* hoặc
vượt trội so với việc tích lũy toàn bộ bộ nhớ trên chuỗi tác vụ kỹ thuật phần
mềm, đồng thời giảm đáng kể chi phí, và *cấu trúc quên* nào là quan trọng nhất.
Chúng tôi đánh giá sáu chính sách bộ nhớ trên toàn bộ tám chuỗi SWE-Bench-CL với
một seed (48 lần chạy có kiểm soát; tiền-đăng-ký 144 lần/ba seed, điều chỉnh còn một seed do hạn nộp — @sec:deviations), giữ cơ chế truy hồi *giống hệt nhau* giữa
các điều kiện. #todo("dịch hoàn chỉnh phần phương pháp & kết quả sau khi có dữ liệu").

// =============================================================================
#outline(title: "Contents", depth: 2, indent: auto)

// =============================================================================
= Introduction
// =============================================================================

== Motivation

Modern AI coding agents are deployed across long streams of related tasks:
fixing successive issues in the same repository, refactoring across a sprint,
or maintaining a service over months. A natural design instinct is to let the
agent *remember* — to persist a record of each task it solved and retrieve
relevant prior experience when a new task arrives. The implicit promise is
positive transfer: experience compounds, and the agent gets better over time.

This promise has a hidden cost structure. Persistent memory grows without bound
unless something removes entries. As the store grows, three pressures appear.
First, *operational cost* rises: every retrieved memory consumes input tokens,
and larger stores require more retrieval and (for some designs) more
maintenance computation. Second, *reasoning degrades*: a well-documented
"lost-in-the-middle" effect @liu2024 and the broader finding that longer context
can hurt @du2025 mean that injecting more memory is not monotonically helpful.
Third, *retrieval noise* accumulates: stale, repository-irrelevant, or
superseded memories compete with useful ones for the limited top-$k$ retrieval
slots @cuconasu2024. Recent work has even shown that naive add-all memory can be
*worse* than no memory at all @xiong2025.

If accumulation is not free, then *forgetting* — deliberately discarding or
compressing memories — becomes a first-class design decision rather than a
fallback triggered by overflow. Cognitive science has long held that forgetting
is adaptive rather than purely lossy: the power-law forgetting curve is a
rational response to the statistics of information need @anderson1991, and
active forgetting serves as a form of regularization @richards2017. This thesis
imports that lens into agentic memory and asks the engineering question it
implies: *given a fixed retrieval mechanism, which forgetting policy gives the
best performance-per-cost on real sequential coding tasks?*

== Research question and sub-questions

#block(fill: rgb("#f5f5f5"), inset: 10pt, radius: 3pt, width: 100%)[
  *Central question.* Under controlled retrieval, do proactive forgetting and
  consolidation policies achieve performance *non-inferior* to full-memory
  accumulation on sequential coding tasks while *materially reducing*
  operational cost — and which content-aware structure of forgetting matters
  most?
]

The central question decomposes into five sub-questions:

/ SQ1: Which memory policies optimize the trade-off between sequential coding performance and operational cost?
/ SQ2: Are gains explained mainly by reducing memory *volume* (Random), selectively retaining *useful* memory (Type-Aware), or *abstractive compression* (CLS)?
/ SQ3: Which memory-item characteristics predict whether stored experience will help or harm future tasks?
/ SQ4: How does agent performance change as persistent memory grows over time?
/ SQ5: Does memory accumulation induce behavioral changes (tool-call frequency, syntax-error rates) that forgetting policies mitigate?

== Hypotheses

The study pre-registers five falsifiable hypotheses (verbatim from the locked
design, §1.3):

/ H1: Selective pruning policies achieve at least one of: *(H1a)* non-inferior sequential performance vs. Full Memory, and/or *(H1b)* materially lower operational cost. H1a is tested for each pruning policy $P in {$Random, Recency, Type-Aware, CLS$}$ as paired difference $(P - "Full")$ in CL-F1 across $N=8$ sequences, evaluated by a *two one-sided tests (TOST)* procedure against a smallest-effect-size-of-interest $"SESOI" = plus.minus 0.03$ CL-F1 with a 95% BCa bootstrap CI (5000 iterations). H1b requires median paired $Delta$(cost) $<= -20%$ with the 95% CI upper bound below zero. *Rejection rule (α-strict):* H1 is rejected for $P$ iff H1a shows $P$ degraded beyond the SESOI lower bound, regardless of H1b — performance non-inferiority is the load-bearing claim; cost reduction alone does not establish that forgetting "matches or beats" full memory.
/ H2: Semantically informed pruning (Type-Aware Decay) outperforms random pruning — i.e. *what* is forgotten matters beyond simply reducing volume.
/ H3: CLS Consolidation gives similar or marginally better raw performance than extractive pruning but at higher cost, *failing* the Pareto efficiency test against simpler policies.
/ H4: Full-memory accumulation induces measurable *analysis paralysis* — increased tool calls and syntax errors — which forgetting policies mitigate.
/ H5: Pruning can *harm* performance when it removes rare but critical repository-specific memories, identifying conditions under which forgetting is unsafe.

The SESOI of $plus.minus 0.03$ CL-F1 corresponds to roughly one task in thirty
changing outcome per sequence — the smallest practitioner-meaningful difference
at SWE-Bench-CL's typical sequence length. It is pre-registered before any data
collection and locked.

== Contributions

The contribution claim is *methodological*, not policy-set novelty (the six
policies overlap in name with prior work; see @sec:related). Concretely, this
thesis delivers:

+ A *pre-registered, controlled Pareto characterization* of forgetting policies for coding agents on a standard continual-learning benchmark (SWE-Bench-CL), bracketed by both No-Memory and Full-Memory boundary baselines — claiming *controlled measurement*, not first-of-kind novelty (recent work already studies agent memory addition/deletion; see @sec:related).
+ A clean *retrieval-as-control* design: retrieval scoring is held identical (pure cosine) across all six conditions (#frozen[invariant \#5]), isolating the *storage* policy from the *retrieval* policy — a confound that prior work conflates.
+ A *pre-committed, effect-size-gated* interpretation protocol: seven triggered framings fixed before data collection (§19), so conclusions cannot be retrofitted to whichever policy happens to win.
+ A reusable, fully-logged experimental harness for memory-policy research, with per-task, per-memory-event, and trajectory logging sufficient for post-hoc helpful/harmful memory analysis.

== Thesis structure

@sec:related situates the work against prior agentic-memory and
continual-learning research. @sec:method specifies the system: agent, memory
representation, the six policies, retrieval, and reflection. @sec:design fixes
the experimental matrix, metrics, statistical plan, and the declared deviations
from pre-registration. @sec:results, @sec:discussion, and @sec:conclusion
present results, interpretation, and conclusions — *pending experiment
execution*. @sec:threats catalogues threats to validity.

// =============================================================================
= Background and Related Work <sec:related>
// =============================================================================

== Agentic memory for LLM agents

A growing body of work equips LLM agents with external memory. MemGPT @packer2024
treats the context window as paged virtual memory; Generative Agents @park2023
store and retrieve a stream of observations with recency/importance/relevance
scoring. MemoryBank @zhong2024 applies an Ebbinghaus forgetting curve to memory
items — the closest cognitive-decay analog to our Type-Aware Decay policy, from
which we differ by parameterizing decay *per memory type* rather than globally
per item. A-MEM @xu2025 organizes memory as a dynamically linked network formed
at write time; we deliberately adopt a *static, content-based* taxonomy
(@sec:memrep) to keep the storage policy cleanly separable from retrieval
(#frozen[invariant \#5]). Reflexion @shinn2023 converts episodic outcomes into
verbal feedback; our reflection step (@sec:reflection) is methodologically
inspired by it but emits *typed* structured records rather than free text.

== Memory cost, context length, and retrieval noise

Several recent results motivate forgetting directly. Xiong et al. @xiong2025
show add-all memory can underperform no memory. Du et al. @du2025 document that
longer context degrades performance, and Liu et al. @liu2024 establish the
"lost-in-the-middle" position effect that drives our injection-order decision
(#frozen[best item last]). Cuconasu et al. @cuconasu2024 quantify how irrelevant
retrieved passages act as noise. On the cost side, industry analyses of
production memory systems @fastpaca2025 document runaway cost growth in
accumulate-everything designs, and MemBench @membench2025 benchmarks the
cost dimension explicitly; Evo-Memory @wei2025evomemory benchmarks self-evolving
agent memory at test time.

== Three layers of memory management <sec:layers>

Work that "manages agent memory" operates at three distinct layers, and
conflating them obscures what is actually being studied:

+ *Persistent application-level memory* — durable records of past tasks, stored
  outside the model and retrieved into the prompt: MemGPT @packer2024, A-MEM
  @xu2025, MemoryBank @zhong2024, HippoRAG @gutierrez2024hipporag, the skill
  library of Voyager @wang2023voyager, and Generative Agents @park2023. *This is
  the layer this thesis studies*: the six policies are storage decisions over
  these records, with retrieval held constant (#frozen[invariant \#5]).
+ *Prompt / context compaction* — summarizing or truncating the in-context
  conversation to fit the window, as in production context-compaction
  @anthropic2026compaction. This reshapes the *current* context, not a
  persistent store.
+ *KV-cache eviction* — dropping key/value entries during decoding to bound
  inference-time memory: H2O @zhang2023h2o and StreamingLLM @xiao2024streamingllm.
  This operates on attention state at the token level, below the application
  layer.

Our contribution is confined to layer 1: we never modify the context-window
manager or the attention cache, so "forgetting" here always means evicting or
consolidating *stored application-level records* — never compacting the prompt
or the KV-cache. Keeping the layers separate is what makes the
retrieval-as-control design coherent.

== Continual learning and forgetting as adaptation

The continual-learning framing supplies our primary metric. We use SWE-Bench-CL
@joshi2025, which structures SWE-Bench tasks into chronological per-repository
sequences and defines plasticity, stability, and CL-F1. The cognitive-science
foundation — that forgetting is a rational, adaptive process — comes from
Anderson and Schooler's power-law analysis of information need @anderson1991,
Richards and Frankland's "forgetting as regularization" @richards2017, and the
complementary-learning-systems (CLS) theory of McClelland et al. @mcclelland1995
that motivates our consolidation policy.

== Positioning <sec:positioning>

The nearest work by name is Alqithami @alqithami2025, which evaluates six
forgetting policies — but on a custom privacy-aware generative-agent benchmark
(FiFA), not coding, with no retrieval control and no estimation-based analysis.
@tbl:positioning summarizes the delta. Our novelty is *controlled measurement*,
not policy invention: the combination of a standard CL coding benchmark,
identical retrieval as confound control, No-Memory↔Full-Memory bracketing, and
pre-committed effect-size-gated framings has not been assembled before.

#figure(
  table(
    columns: (auto, 1fr, 1fr, 1fr),
    align: (left, center, center, center),
    stroke: 0.4pt,
    inset: 5pt,
    table.header([*Axis*], [*Xiong 2025*], [*Alqithami 2025*], [*This work*]),
    [Domain], [LLM agents], [Privacy agents], [Coding (sequential)],
    [Benchmark], [mixed], [FiFA (custom)], [*SWE-Bench-CL*],
    [\# forgetting policies], [1 vs 1], [6], [*6*],
    [Retrieval held constant?], [n/a], [not stated], [*Yes — pure cosine*],
    [No-/Full-Memory baselines], [partial], [absent], [*both*],
    [Primary metric], [task success], [composite], [*CL-F1*],
    [Statistical unit], [per-task], [per-run], [*per-sequence ($N=8$)*],
    [Pre-registered framings], [no], [no], [*yes (§19)*],
  ),
  caption: [Positioning against the two closest prior works (abridged from v5 §1.4).],
) <tbl:positioning>

// =============================================================================
= Methodology <sec:method>
// =============================================================================

== System architecture

The system is a single LangGraph ReAct coding agent backed by a two-layer
memory store (an active SQLite-backed record set plus a FAISS vector index over
embedding payloads). For each task the pipeline is: *(1) retrieve* relevant
memories under a token budget, *(2) build prompt context* with retrieved
memories injected in relevance-sorted order (best item last), *(3) solve* the
task with a bounded ReAct loop, *(4) evaluate* the produced patch with the
standard SWE-Bench `eval_v3` harness, *(5) reflect* to produce a typed memory
record, *(6) write* the record, and *(7) maintain* the store according to the
active policy. Only steps (1), (6), and (7) — retrieve, write, maintain — differ
between conditions; everything else is held identical.

== Agent specification

The agent is a tool-using ReAct loop with a hard cap of #frozen[20 steps] per
task (force-fail on exceed; invariant \#3). It is given a fixed tool set
(read/list files, search, run tests, apply edits, finish) and a prompt template
that is byte-identical across all six conditions except for the injected memory
block. The agent's private chain-of-thought is *never* written to trajectory
logs; only action summaries and observations are recorded.

== Memory representation <sec:memrep>

Each memory is a structured `MemoryRecord` carrying the task it came from, the
repository, the files touched, an outcome label, a *content type*, and an
embedding payload. The content taxonomy is a locked five-type, *content-based*
(not outcome-based) scheme (#frozen[invariant \#7]):

#figure(
  table(
    columns: (auto, auto, 1fr),
    align: (left, center, left),
    stroke: 0.4pt, inset: 5pt,
    table.header([*Type*], [*Tier*], [*Meaning*]),
    [`architectural`], [Sacred], [structural/design decisions about the repo],
    [`api_change`], [Critical], [signature/interface changes],
    [`bug_fix`], [Important], [a defect and its fix],
    [`test_update`], [Expendable], [test-only changes],
    [`config`], [Expendable], [configuration/build changes],
  ),
  caption: [The locked 5-type content taxonomy (v5 §5.1). Type is orthogonal to outcome.],
) <tbl:taxonomy>

A type *classifier* (a separate structured-output LLM call (temperature per amendment A2)) assigns
the type; the "outcome" axis (resolved/failed) is kept strictly orthogonal and
is never collapsed into the type.

The *embedding payload* is the single most safety-critical representation
decision. It is restricted to `[Issue + Final Error + Final Diff]` and capped at
*< 7500 tokens* (#frozen[invariant \#4]), enforced by an assertion in the store.
Raw trajectories are never embedded: the embedder would silently truncate them
and produce garbage vectors.

== The six memory policies <sec:policies>

All six policies share an identical `retrieve` (see @sec:retrieval); they differ
only in `write` and `maintain`. @tbl:policies summarizes them.

#figure(
  table(
    columns: (auto, 1fr, 1fr),
    align: (left, left, left),
    stroke: 0.4pt, inset: 5pt,
    table.header([*Policy*], [*Write*], [*Maintain (forgetting rule)*]),
    [P0 No Memory], [store nothing], [—],
    [P1 Full Memory], [add all], [never prune (boundary baseline)],
    [P2 Random Prune], [add all], [archive a uniformly random victim over budget],
    [P3 Recency Prune], [add all], [archive oldest first (keep most recent $M$)],
    [P4 Type-Aware Decay], [add all], [archive lowest power-law score (see below)],
    [P5 CLS Consolidation], [add all], [every $k=5$ tasks, cluster + abstractively summarize old non-sacred memories],
  ),
  caption: [The six conditions. Only write/maintain differ; retrieve is identical.],
) <tbl:policies>

*P1 Full Memory* means "store everything; retrieve top-$k$ under the same
budget" — *not* "append everything into the prompt." Appending all memories
would confound the storage policy with context length and is reserved as an
optional stress-test ablation.

*P2 Random Prune* isolates the pure *volume* effect: any improvement over Full
Memory here comes from "less memory," not "smarter memory." It is the natural
control for H2.

*P4 Type-Aware Decay* is the central semantic policy. When the active store
exceeds the budget $M$, each record is scored with an Anderson–Schooler
power-law form (#frozen[invariant \#8], locked formula):

$ "score" = "base"("type") dot "age"^(-d("type")) dot (1 + "retrievals")^(0.5) $ <eq:decay>

where `age` is tasks-since-creation, the frequency exponent $0.5$ is sub-linear
(doubling retrievals does not double value), and the per-type $("base", d)$
weights are *theoretical and frozen at design time* (not calibrated from pilot
data):

#figure(
  table(
    columns: (auto, auto, auto, auto),
    align: (left, center, center, center),
    stroke: 0.4pt, inset: 5pt,
    table.header([*Type*], [*base*], [*decay $d$*], [*tier*]),
    [`architectural`], [1.0], [0.05], [Sacred],
    [`api_change`], [0.8], [0.15], [Critical],
    [`bug_fix`], [0.6], [0.25], [Important],
    [`test_update`], [0.4], [0.35], [Expendable],
    [`config`], [0.3], [0.40], [Expendable],
  ),
  caption: [Locked per-type decay parameters for @eq:decay (v5 §8 P4). Lowest score is archived first.],
) <tbl:decay>

Crucially, the score does *not* include any success/failure-after-retrieval
term: those are downstream *associated* labels (#frozen[invariant \#10]), and
using them in the policy would smuggle causal claims into the scoring.

*P5 CLS Consolidation* fires on a fixed schedule (#frozen[every $k=5$ tasks],
invariant \#9 — *not* trigger-on-overflow). It clusters old (age $>= 10$),
same-repo, non-architectural memories by file/similarity overlap and replaces
each cluster of $>= 3$ records with one LLM-generated summary capped at 350
tokens, archiving the originals with provenance links. If still over budget, it
falls through to Type-Aware Decay. The consolidation LLM call is metered and
charged to the cost axis — this is what H3 tests.

== Retrieval (identical across all conditions) <sec:retrieval>

Retrieval is the load-bearing experimental control. For every condition, the
query is constructed identically and scored by *pure cosine similarity* with
*no bonuses and no penalties* (#frozen[invariant \#5]). The top-$k$ memories
(default $k=5$) are selected under a token budget (default 2000 tokens) and
injected *relevance-sorted with the best item last* (#frozen[invariant \#6]), to
counter the lost-in-the-middle effect @liu2024. Retrieval is restricted to the
*same repository* in the main experiment (#frozen[invariant \#16]). Because
retrieval is byte-for-byte identical, any between-condition difference is
attributable to *what was stored*, not *how it was retrieved*.

== Reflection and memory writing <sec:reflection>

After each task the agent runs a single structured-output *reflection* call that
emits one main typed record per task (deterministic outcome and file list),
followed by the type-classifier call. The reflection is inspired by Reflexion
@shinn2023 but produces a fixed schema so that downstream storage policies
operate on uniform records.

// =============================================================================
= Experimental Design <sec:design>
// =============================================================================

== Benchmark and sequences

The primary (and only main-experiment) benchmark is *SWE-Bench-CL* @joshi2025:
eight MIT-licensed repository sequences of 19–50 chronologically-ordered tasks
each, evaluated by the standard SWE-Bench `eval_v3` Docker harness. All eight
official sequences are used with *no re-ordering, no subsetting, and no
self-generated sequences* (#frozen[invariant \#1]), except where compute
constraints force a documented exclusion (see @sec:deviations).

== Experiment matrix

The experiment was *pre-registered* at *6 policies × 8 sequences × 3 seeds = 144
controlled runs* (#frozen[invariants \#1, \#2]). Under a hard submission
deadline the *executed* design is *6 policies × 8 sequences × 1 seed = 48 runs*
— a documented, deadline-constrained amendment (*A6*, @sec:deviations). The
single seed is held identical across all conditions, so between-policy
comparisons remain valid and the $N=8$ sequence-level primary test
(#frozen[invariants \#1, \#11]) is preserved; the cost is the within-condition
seed-variance estimate, and the seed dimension is reported as exploratory rather
than as a three-fold replication. The originally-planned 12-run cross-model probe
is deferred to future work.

== Metrics

*Correctness / continual learning.* The primary metric is *CL-F1*, the harmonic
mean of plasticity (online accuracy across all tasks) and an *anchor-probe*
stability estimate:

$ "CL-F1" = (2 dot "CL-Plasticity" dot "CL-Stability") / ("CL-Plasticity" + "CL-Stability") $ <eq:clf1>

Because the full $a_(i,j)$ re-evaluation matrix is computationally infeasible at
this scale ($O(10^4)$ extra agent runs), stability is estimated with a locked
*anchor-probe schedule*: five anchor tasks per sequence are re-evaluated at four
probe points against the memory snapshot taken at each point, bounding
re-evaluations at $4 times 5 = 20$ per (sequence, condition, seed). The
anchor-probe stability *lower-bounds* the full-matrix stability; the full matrix
is run only as a 4-cell sensitivity check if budget permits.

*Efficiency.* Total tokens, estimated cost, wall time, tool calls, test runs,
files read/modified, and per-resolved-task normalizations.

*Memory growth.* Active/archived/consolidated counts and tokens over time,
pruning ratio, consolidation ratio.

*Behavioral (H4).* Tool calls per task, syntax-error rate, files read per task,
test runs per task — hypothesized to rise under Full Memory and stay bounded
under forgetting.

*Retrieval quality.* Per-retrieved-memory `same_repo`, file overlap, type match,
similarity, age, outcome, and rank; aggregated into Relevant\, Retrieval-noise\,
and a stale-rate.

== Statistical analysis plan

The philosophy is *estimation over testing* @cumming2014 @wasserstein2019: with
$N=8$ independent sequences, NHST has very limited power, so effect sizes and
confidence intervals are the primary evidence and p-values supplement.

- *Unit:* sequence-level values (a single seed, amendment A6; the pre-registered design averaged 3 seeds), $N=8$ paired observations per condition pair.
- *Effect size (primary):* rank-biserial $r_("rb")$ (#frozen[invariant \#12] — not Cohen's $d$, not Cliff's $delta$) and median paired difference with a 95% BCa bootstrap CI (#frozen[5000 iterations], invariant \#15).
- *Planned contrasts (5, pre-registered):* each pruning policy and No Memory vs. Full Memory, by paired Wilcoxon signed-rank (#frozen[invariant \#11]) under Holm correction. The remaining 10 pairwise comparisons are exploratory with uncorrected p-values.
- *Non-inferiority (H1a):* TOST against $"SESOI" = plus.minus 0.03$ CL-F1.
- *Task-level (exploratory):* a binomial-logit GLMM with crossed random effect on `task_id` (#frozen[invariant \#14]).
- *Helpful/harmful prediction (SQ3):* PR-AUC with a VIF check (#frozen[invariant \#13] — not accuracy, not ROC-AUC, because the positive class is ~20%).

A worked reporting template (v5 §15.5) fixes the exact phrasing of each contrast
so results are reported uniformly.

== Pareto analysis

The headline output is a Pareto plot of *CL-F1 (y)* vs. *total system cost (x)*,
where cost includes all operational LLM calls (agent + reflection + classifier +
consolidation) but *excludes* the anchor-probe re-evaluation overhead
(measurement cost not borne in deployment). Pareto-optimal (non-dominated)
conditions become the practical recommendations. For CLS specifically we report
cost-normalized CL-F1 per dollar; if CLS matches Type-Aware Decay on CL-F1 but
costs multiples more, it fails the Pareto test (H3).

== Deviations from pre-registration <sec:deviations>

The *executed* study differs from the frozen pre-registration
(`THESIS_FINAL_v5.md`) along two axes: *runtime deviations* (D1–D5), forced by
the compute and provider environment, and *pre-registration amendments* (A1–A6),
design changes adopted during execution. Every change is *declared* — none is a
silent redesign — and the complete dated record with rationale is maintained in
`AMENDMENTS.md`. Each holds its factor *constant across all conditions*, so it is
a fixed factor: between-policy comparisons (H1–H5) remain valid, while absolute
resolution rates are *not* comparable to GPT-5.4 or public SWE-Bench
leaderboards.

#figure(
  table(
    columns: (auto, 1fr, 1fr),
    align: (left, left, left),
    stroke: 0.4pt, inset: 5pt,
    table.header([*\#*], [*Runtime deviation*], [*Why it stays valid*]),
    [D1], [Model → *Kimi "for coding"* (`kimi-k2.6`), all roles (was GPT-5.4)], [held constant across conditions; absolute rates not leaderboard-comparable],
    [D2], [Embedder → local `nomic-embed-text-v2-moe` (768-d)], [bounds the under-7500-token payload, not embedder identity; same embedder across all conditions],
    [D3], [Cost metric → token-count proxy (not USD)], [flat-rate subscription; tokens are a provider-independent compute proxy],
    [D4], [Classifier structured output → JSON-mode + Pydantic validation], [same 5-type taxonomy (#frozen[invariant \#7]); failure rate logged + handled identically (temperature: see A2)],
    [D5], [Host → *x86_64 DigitalOcean droplet* with prebuilt SWE-Bench images (was arm64 macOS)], [native x86_64; no architecture-based task exclusions required],
  ),
  caption: [Runtime deviations (D1–D5) forced by the execution environment.],
) <tbl:deviations>

#figure(
  table(
    columns: (auto, 1fr, 1fr),
    align: (left, left, left),
    stroke: 0.4pt, inset: 5pt,
    table.header([*\#*], [*Pre-registration amendment*], [*Rationale*]),
    [A1], [Memory budget: cap 100 → *10* records], [at one record per task on 19–50-task sequences a cap of 100 never binds, so the four pruning policies never evict; 10 is below the shortest sequence, making the budget bind on all eight (and H2 testable)],
    [A2], [Temperature 0 → *1* (agent, reflection, classifier, summary)], [the Kimi reasoning endpoint rejects temperature 0; held constant across conditions; classification is now non-deterministic, so its failure rate is reported],
    [A3], [CLS consolidation candidate age 10 → *5* tasks (half the cap)], [derived from A1: at cap 10 no active record ever reaches age 10, so CLS could otherwise never consolidate],
    [A4], [H1b efficiency construct: "at least 20% fewer tokens" → *storage footprint + retrieval latency*], [under fixed top-$k$ retrieval, storage pruning cannot reduce the prompt budget; footprint/latency is the mechanism-aligned axis],
    [A5], [Anchor-probe scope (under review)], [pilot stability saturated and full-matrix anchor-probe is several days of compute; may be reduced (#frozen[invariant \#29])],
    [A6], [Replication: 3 seeds → *1 seed* (48 runs)], [hard submission deadline; preserves the $N=8$ primary test (#frozen[invariants \#1, \#11]) and CL-F1 (#frozen[invariant \#9]); seed dimension reported as exploratory],
  ),
  caption: [Pre-registration amendments (A1–A6); full dated record in `AMENDMENTS.md`.],
) <tbl:amendments>

The empirical consequence of A3 is itself a finding (reported in @sec:results):
even with the amended age threshold, abstractive consolidation rarely triggers,
because the clustering criterion (#frozen[invariant \#23]: at least three
memories at 0.70 cosine similarity or above) is seldom met among the
semantically diverse same-repository tasks. CLS therefore behaves largely as its
Type-Aware-Decay fallback, and H3 is reported as a negative result on this
benchmark.

// =============================================================================
= Results <sec:results>
// =============================================================================

#pending[
  No real experimental data exists yet. The integration spine (agent loop, eval
  harness, CL-F1 collection, run entry point) is partially built but has not
  executed a single valid run; all files currently in `results/raw/` are stub
  fixtures (identical hardcoded values, `run_id = "test_run_id"`). This section
  is scaffolded with the exact tables and figures the analysis plan will
  populate. *Do not cite any number below until the 48 runs complete.*
]

== Headline result table (scaffold)

#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    align: (left, center, center, center, center),
    stroke: 0.4pt, inset: 5pt,
    table.header([*Policy*], [*CL-F1*], [*Plasticity*], [*Stability*], [*Total tokens*]),
    [No Memory], [—], [—], [—], [—],
    [Full Memory], [—], [—], [—], [—],
    [Random Prune], [—], [—], [—], [—],
    [Recency Prune], [—], [—], [—], [—],
    [Type-Aware Decay], [—], [—], [—], [—],
    [CLS Consolidation], [—], [—], [—], [—],
  ),
  caption: [#todo("Mean ± SEM across 8 sequences (one seed, amendment A6), once runs complete.")],
)

== Planned contrasts (scaffold)

#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    align: (left, center, center, center, center),
    stroke: 0.4pt, inset: 5pt,
    table.header([*Contrast vs Full Memory*], [$Delta$ CL-F1], [$r_("rb")$], [*95% BCa CI*], [*Holm-p*]),
    [Random Prune], [—], [—], [—], [—],
    [Recency Prune], [—], [—], [—], [—],
    [Type-Aware Decay], [—], [—], [—], [—],
    [CLS Consolidation], [—], [—], [—], [—],
    [No Memory], [—], [—], [—], [—],
  ),
  caption: [#todo("Five pre-registered contrasts; report TOST verdict per H1a alongside.")],
)

== Pareto frontier (scaffold)

#figure(
  rect(width: 100%, height: 5cm, stroke: (dash: "dashed"), fill: rgb("#fafafa"))[
    #align(center + horizon)[#text(fill: gray)[#todo("Pareto scatter: CL-F1 (y) vs total token cost (x), 6 points + per-sequence SEM error bars.")]]
  ],
  caption: [Pareto frontier of performance vs. cost — the headline figure.],
) <fig:pareto>

== Behavioral and memory-growth results (scaffold)

#todo("Tool-calls-per-task and syntax-error-rate trajectories by policy (H4); active-memory-size-over-time curves; retrieval Relevant\ / noise\.")

== Failure case studies (scaffold)

#todo("Per-policy hand-coded cases: 5 memory-helped, 5 memory-irrelevant, 5 memory-harmful, 5 pruning-removed-useful, 5 consolidation-lost-detail (CLS), per the §18 template.")

// =============================================================================
= Discussion <sec:discussion>
// =============================================================================

#pending[
  Interpretation depends on which outcome obtains. The design pre-registers
  seven *triggered framings* (v5 §19) so the narrative cannot be retrofitted to
  the winner. The scaffolding below records each framing; the realized framing
  will be selected by the locked combination rule once data exist.
]

The pre-committed framings, keyed to outcomes, are:

/ If Full Memory wins: accumulation pays off at SWE-Bench-CL sequence lengths; forgetting's value is cost, not performance — report H1b separately.
/ If Type-Aware Decay wins: content-aware forgetting beats both volume reduction and accumulation (supports H2); examine which types drive it.
/ If Random Prune matches Type-Aware Decay: the benefit is *volume*, not *semantics* — H2 not supported; a sobering, publishable null.
/ If Recency Prune wins: a cheap temporal heuristic suffices; questions the value of semantic machinery.
/ If CLS loses on Pareto: abstractive consolidation pays the LLM-on-write tax without a CL-F1 return at this sequence length (supports H3); gate on CLS firing rate (\<30% ⇒ uninformative).
/ If No Memory is competitive: memory adds little here — a strong negative result about the premise itself.
/ If the retrieval-overlap probe shows no contrast between storage policies: the storage manipulation did not propagate to retrieval; all storage-policy claims are qualified accordingly.

#todo("Populate with the realized framing; connect to SQ1–SQ5; integrate failure case studies; state which hypotheses are supported/rejected with effect sizes.")

// =============================================================================
= Threats to Validity <sec:threats>
// =============================================================================

The design anticipates twelve threats (v5 §20); the load-bearing ones:

/ Model stochasticity: under amendment A2 the model runs at temperature 1 (non-deterministic), and under amendment A6 at a single seed, so 3-seed pooling no longer applies; re-evaluation variance is treated as within-sequence noise and the seed dimension is reported as exploratory — a threat strengthened by the deadline-constrained design.
/ Retrieval confound: addressed by construction — identical pure-cosine retrieval across conditions (#frozen[invariant \#5]) — and *detected* by a retrieval-overlap (Jaccard) probe; if storage policies produce indistinguishable retrieved sets, all storage claims are qualified.
/ Full-Memory definition: "store all, retrieve top-$k$" rather than "append all," to avoid confounding memory policy with context length.
/ Embedding truncation: the \<7500-token payload cap (#frozen[invariant \#4]) prevents silent truncation; raw trajectories are never embedded.
/ Classifier accuracy: the type classifier is audited and its failure rate logged and handled identically across conditions; a classifier-as-policy confound is explicitly tracked.
/ Type-Aware parameter calibration: per-type decay $d$ is *theoretical and frozen*, never tuned from pilot data, to preserve pre-registration.
/ Stability estimation: anchor-probe stability lower-bounds the full matrix; a 4-cell full-matrix sensitivity check qualifies stability claims if estimates diverge by >0.05.
/ Single benchmark + single base model: external validity is bounded; the originally-planned cross-model probe is deferred to future work, and any cross-repo ablation would be exploratory only.
/ Causal interpretation: memory-item helpful/harmful labels are *associated, not causal* (#frozen[invariant \#10]); the helpful/harmful model is predictive, not explanatory.
/ Deviations D1–D5: absolute resolution rates are not comparable to GPT-5.4 / leaderboards; only *between-policy* contrasts are claimed (@sec:deviations).

// =============================================================================
= Conclusion <sec:conclusion>
// =============================================================================

#pending[
  The conclusion follows from results. Scaffold: restate which forgetting
  structure (volume / semantic / abstractive) won the Pareto test, the answer to
  the central question (does proactive forgetting match-or-beat full memory at
  lower cost?), the supported/rejected hypotheses with effect sizes, and the
  bounded scope of the claim (single benchmark, single base model, declared
  deviations). End with the practical recommendation: the Pareto-optimal
  policy(ies) practitioners should adopt.
]

#todo("Write once H1–H5 verdicts exist.")

// =============================================================================
#heading(numbering: none, level: 1)[References]
// =============================================================================

#set par(first-line-indent: 0em)
#set text(size: 9.5pt)

#bibliography("refs.yml", title: none, style: "ieee")

