# Presentation Upgrade Playbook — Thesis Report (LaTeX)

> One prioritized, copy-pasteable plan to close the "looks unfinished" gap.
> Every item is grounded in our actual files and the example thesis (`example_contents`).
> No fabricated numbers anywhere; never fill a pending result table with invented data.

---

## 0. Honest diagnosis (read this first)

**Our report looks unfinished mainly because it _is_ a deliberate progressive draft — not because of bad typography.**

The example thesis (`example_contents`) and our draft use the **same default LaTeX look**: both are plain Computer Modern, both lean on `booktabs`, neither uses exotic fonts. Side by side at the glyph level there is no typographic gap. What makes the example *read* as finished and ours read as in-progress is concrete and enumerable:

1. **Placeholder scaffolding is the dominant "unfinished" signal.** Our draft carries **11 `todobox`, 3 `figurestub`, 18 `[RESULT: pending]` inline markers, and 2 all-`---` tables**, concentrated in the entire Results chapter (5.1–5.7), Discussion 6.1–6.2, both Conclusion sections, and both appendices. Chapters 1–4 are finished prose. This is correct and honest — those gaps await the 144-run results — but the *visual language* of "pending" is inconsistent (yellow box vs blue box vs raw `[RESULT:]` vs bare `---`), and bare `---` cells read as typesetting errors rather than deliberate placeholders.
2. **Figures carry tool chrome.** Our two diagrams are real vector PDFs (Skia/PDF) but we embed their **72-dpi PNG rasters** with the **Archify UI footer** ("Built with Archify · Press T for theme") and dead canvas margins baked in. That chrome — not resolution and not fonts — is the amateur tell.
3. **Front matter is bare.** Empty `\author{}`, no university/department/degree/date, no `\listoffigures`/`\listoftables`. A finished thesis always ships these; they are content-free and high-impact.
4. **Tables and math are under-scaffolded for the look the example achieves** — plain `booktabs` with no `siunitx` decimal alignment, no `\resizebox` on wide tables; and Chapter 4 (Methodology) has **zero numbered display equations** despite being intrinsically mathematical.

None of this is a font problem. The fix is **scaffolding density + a handful of craft items**, almost all of which are presentation-safe and need no results. The few that need the 144 runs are tagged `[WHEN-144-LANDS]` and are *structural* (column types, plot includes) — never invented numbers.

---

## 1. The big four — do these first (largest "looks finished" payoff)

If you do nothing else, do these. Each is `[DO NOW]`, low-risk, and closes most of the perceived gap.

| # | Change | Why it's top-4 | File |
|---|---|---|---|
| **BIG-1** | **Fill the title page + add LoF/LoT** | First page seen; bare `\author{}` screams draft. LoF/LoT signal a complete, figure-dense document. | `main.tex` |
| **BIG-2** | **Swap figure PNG→PDF, crop the Archify chrome, move in-image text into captions** | Removes the single most amateur tell (UI chrome) and the soft-raster look in one pass; we already own the vector PDFs. | `4.1_Controlled-Comparison-Design.tex`, `4.2.0_Overview.tex`, `figures/*.pdf` |
| **BIG-3** | **Make "pending" deliberate + unify the placeholder visual language** | Bare `---` and three competing pending styles are what make the draft read as broken vs. intentionally staged. | `preamble.tex` + Results/Discussion/Conclusion files |
| **BIG-4** | **Renumber/relabel/gloss the Type-Aware Decay equation (Invariant #8) + add the cosine equation (Invariant #5)** | Converts the thesis's two signature laws from code-like asides into citable, defensible display math. Highest polish-per-edit in the methodology. | `4.2.5_Type-Aware-Decay.tex`, `4.4_Retrieval-Fixed-Invariant.tex`, `preamble.tex` |

Everything below expands these and adds the rest, in priority order.

---

## 2. Front matter & preamble polish (all `[DO NOW]`, presentation-safe)

### 2.1 `[DO NOW]` Title page — `main.tex`
Bare `\author{}` and a misused `\date` are the loudest draft signal. Replace the `titlepage` block:
```latex
\begin{titlepage}
  \centering
  \vspace*{2.5cm}
  {\LARGE\bfseries Memory Pruning and Forgetting Policies\\
   for AI Coding Agents\par}
  \vspace{0.6em}
  {\large Impact on Performance Across Sequential Tasks\par}
  \vspace{2.5cm}
  {\large A thesis submitted in partial fulfillment\\
   of the requirements for the degree of\\
   Master of Science\par}
  \vspace{2cm}
  {\large\itshape <Author Name>\par}          % metadata to fill, not a result
  \vspace{0.4em}
  {\normalsize <Department, University>\par}
  \vspace{0.4em}
  {\normalsize Supervisor: <Name>\par}
  \vfill
  {\normalsize \today\par}
\end{titlepage}
```
The `<...>` are metadata placeholders to fill, not fabricated data.

### 2.2 `[DO NOW]` List of Figures / List of Tables + clean page breaks — `main.tex`
Add right after `\tableofcontents`:
```latex
\tableofcontents\clearpage
\listoffigures\clearpage
\listoftables\clearpage
```
`figurestub` boxes correctly do **not** appear (they aren't `\caption`s) — pending figures shouldn't claim a LoF entry. Real `\caption`s populate automatically and degrade gracefully while results are stubbed.

### 2.3 `[DO NOW]` Caption styling — `preamble.tex`
Default `book` captions are heavy and undifferentiated. Make the label stand out:
```latex
\usepackage[font=small,labelfont=bf,labelsep=period,textfont=it,skip=6pt]{caption}
```

### 2.4 `[DO NOW]` Running headers — `preamble.tex`
A 7-chapter thesis benefits from navigation context on every page:
```latex
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0.4pt}
\fancyhead[L]{\nouppercase{\leftmark}}
\fancyhead[R]{\thepage}
\fancypagestyle{plain}{\fancyhf{}\fancyfoot[C]{\thepage}\renewcommand{\headrulewidth}{0pt}}
```

### 2.5 `[DO NOW]` Robust cross-refs — `preamble.tex` (load AFTER `hyperref`)
```latex
\usepackage{cleveref}   % must come after hyperref
% then "\cref{tab:main-results}" auto-supplies "Table"; keeps type words consistent
```

### 2.6 `[DO NOW]` Refined chapter heads (optional, the only item that changes a default *look*) — `preamble.tex`
```latex
\usepackage{titlesec}
\titleformat{\chapter}[hang]{\normalfont\huge\bfseries}{\thechapter}{0.6em}{}
\titlespacing*{\chapter}{0pt}{10pt}{24pt}
```
If you want to stay maximally conservative, skip this one — it is cosmetic, not missing scaffolding.

### 2.7 `[DO NOW]` `\texttt` color balance + paragraph cue — `preamble.tex`
We use `\texttt` heavily for identifiers (`full\_memory`, `THESIS\_FINAL\_v5`). CM typewriter renders large next to CM roman; even the page color:
```latex
\let\oldtexttt\texttt
\renewcommand{\texttt}[1]{{\small\ttfamily #1}}
```
Also: if both `parindent` and `parskip` are set, pick one paragraph cue (indent **or** spacing, not both) to remove the double cue.

### 2.8 `[DO NOW]` Bibliography hygiene — `main.tex`
Replace `\nocite{*}` (dumps the entire `.bib`) with explicit `\nocite{key1,key2}` for anything genuinely uncited-but-relevant, or remove it. Confirm `\bibliographystyle{plain}` is the intended style.

---

## 3. Figure craft

Crucial fact: `figures/architecture.pdf` and `figures/task-lifecycle.pdf` are **genuine vector** (Skia/PDF, embedded vector fonts). The currently-embedded `.png`s are their 72-dpi raster twins. So the fix is mostly include-swap + crop, not redraw.

### 3.1 `[DO NOW]` Swap PNG → vector PDF
`Chapter_4-Methodology/4.1_Controlled-Comparison-Design.tex` (the `\includegraphics` near line 44):
```latex
\includegraphics[width=\textwidth]{architecture.pdf}    % was architecture.png
```
`Chapter_4-Methodology/4.2_Six-Memory-Policies/4.2.0_Overview.tex` (near line 56):
```latex
\includegraphics[width=\textwidth]{task-lifecycle.pdf}  % was task-lifecycle.png
```
`graphicspath` already includes `figures/` (`preamble.tex`), and pdfLaTeX picks the PDF automatically.

### 3.2 `[DO NOW]` Crop the Archify chrome + dead margins (lossless, vector)
The footer ("Built with Archify · Press T…"), dotted grid, and outer rounded border are the amateur tell. Crop them:
```bash
# preferred: pdfcrop (TeX Live). margins in pt.
pdfcrop --margins 4 figures/architecture.pdf figures/architecture.pdf
pdfcrop --margins 4 figures/task-lifecycle.pdf figures/task-lifecycle.pdf

# fallback if pdfcrop absent (Ghostscript): get the tight box, then re-export
gs -dQUIET -dBATCH -dNOPAUSE -sDEVICE=bbox figures/architecture.pdf 2>&1 | grep HiResBoundingBox
```
If the Archify footer sits *inside* the content bbox (so cropping the margin won't remove it), **re-export from Archify with chrome off**, or redraw (3.4). At minimum crop the dead outer margin so the boxes fill `\textwidth`.

### 3.3 `[DO NOW]` Move in-image text panels into the caption
The "Agent loop / Retrieval held constant / The only variable" cards baked into the PNG duplicate prose, aren't searchable/translatable, and aren't CM type. Delete them from the figure; the architecture caption already carries the same point. Keep figures to **boxes + arrows + a minimal legend**; let LaTeX own the words.

### 3.4 `[DO NOW, optional/high-polish]` Redraw the architecture diagram in TikZ
Worth it for the signature figure: CM typography, crisp vector, no chrome, git-diffable. Add to `preamble.tex`:
```latex
\usepackage{tikz}
\usetikzlibrary{positioning,arrows.meta,fit,backgrounds}
\definecolor{cAgent}{HTML}{2E7D6B}
\definecolor{cFixed}{HTML}{6B5BA8}
\definecolor{cPolicy}{HTML}{C2185B}
```
Drop-in replacement for the `\includegraphics` in `4.1_Controlled-Comparison-Design.tex`:
```latex
\begin{figure}[htbp]
\centering
\begin{tikzpicture}[
  font=\small,
  box/.style={draw, rounded corners=2pt, align=center, minimum height=9mm,
              minimum width=22mm, inner sep=4pt, thick},
  fixed/.style={box, draw=cFixed},
  agent/.style={box, draw=cAgent, line width=0.6pt},
  policy/.style={box, draw=cPolicy, line width=1pt},
  flow/.style={-{Stealth[length=2.2mm]}, thick},
  hold/.style={-{Stealth[length=2.2mm]}, thick, dashed, draw=cPolicy},
  node distance=10mm and 16mm,
]
  \node[box]                  (data)  {SWE-Bench-CL\\\scriptsize task sequence};
  \node[agent, right=of data] (agent) {Coding Agent\\\scriptsize LangGraph ReAct, $\le$20 steps};
  \node[fixed, right=of agent](retr)  {Cosine Retriever\\\scriptsize fixed top-$k$, identical};
  \node[fixed, right=of retr] (store) {MemoryStore\\\scriptsize FAISS index};
  \node[box, above=of agent]  (llm)   {deepseek-v4-flash\\\scriptsize frozen, all roles};
  \node[box, below=of agent]  (eval)  {eval\_v3 harness\\\scriptsize scores the patch};
  \node[fixed, above=of store](policy){Forgetting Policy\\\scriptsize 1 of 6 -- swappable};
  \node[fixed, below=of store](refl)  {Reflection + Classifier\\\scriptsize 5-type taxonomy};
  \draw[flow] (data)  -- (agent);
  \draw[flow] (agent) -- node[above,font=\scriptsize]{retrieve} (retr);
  \draw[flow] (retr)  -- node[above,font=\scriptsize]{top-$k$} (store);
  \draw[flow] (agent) -- node[right,font=\scriptsize]{LLM calls} (llm);
  \draw[flow] (agent) -- node[right,font=\scriptsize]{patch} (eval);
  \draw[flow] (refl)  -- node[right,font=\scriptsize]{store record} (store);
  \draw[hold] (policy)-- node[right,font=\scriptsize]{maintain / forget} (store);
  \begin{scope}[on background layer]
    \node[draw=cFixed!60, dashed, rounded corners, inner sep=6mm,
          label={[font=\scriptsize, text=cFixed]above:Memory subsystem (retrieval held constant)},
          fit=(retr)(store)(policy)(refl)] {};
  \end{scope}
\end{tikzpicture}
\caption{The memory-equipped coding agent. The model, embedder, retrieval, dataset, and
agent loop are held constant; the forgetting \emph{policy} (red) is the single swappable
component, one of six.}
\label{fig:architecture}
\end{figure}
```
Leave `task-lifecycle` as cropped vector PDF unless time permits. Do **not** redraw matplotlib plots in TikZ — export those to PDF.

### 3.5 `[WHEN-144-LANDS]` Pareto / results plots as subfigure grids
Needs `\usepackage{subcaption}` in `preamble.tex` (also `\usepackage{float}` if you want `[H]`). Keep `figurestub` placeholders until the real `results/plots/*.pdf` exist — do not invent plots.
```latex
\begin{figure}[htbp]
    \centering
    \begin{subfigure}[b]{0.48\textwidth}
        \centering
        \includegraphics[width=\textwidth]{pareto_compute.pdf}
        \caption{CL-F1 vs.\ compute (tokens)}\label{fig:pareto_compute}
    \end{subfigure}\hfill
    \begin{subfigure}[b]{0.48\textwidth}
        \centering
        \includegraphics[width=\textwidth]{pareto_footprint.pdf}
        \caption{CL-F1 vs.\ memory footprint}\label{fig:pareto_footprint}
    \end{subfigure}
    \caption{Pareto frontiers across the six policies. (a) compute axis; (b) footprint axis.}
    \label{fig:pareto}
\end{figure}
```
For a 6-panel per-policy grid, lay out 2×3 with `\\` between rows; add `\ContinuedFloat` + "(continued)" if it breaks across pages.

---

## 4. Table styling

The example's polish comes from **consistency**, not exotic packages — plain `booktabs` + six idioms. All applicable now to our `---` placeholder tables so structure is professional before numbers land.

### 4.1 `[DO NOW]` Enforce booktabs three-rule discipline everywhere
`\toprule … \midrule … \bottomrule`, **never `\hline`, never vertical `|` rules**. This is the single largest contributor to the clean look. Audit all six of our tables for stray `\hline`/`|`.

### 4.2 `[DO NOW]` Add table-scaling + alignment packages — `preamble.tex`
```latex
\usepackage{booktabs}   % if not already present
\usepackage{siunitx}
\sisetup{detect-all, table-number-alignment=center,
         round-mode=places, round-precision=3}
% \resizebox is part of graphicx (already loaded)
```

### 4.3 `[DO NOW]` Two reusable templates (degrade gracefully on `---`)
**A. Simple comparison (3–4 cols, no resizebox):**
```latex
\begin{table}[htbp]
    \centering
    \caption{One-sentence description, ending with eval context.}
    \label{tab:KEY}
    \renewcommand{\arraystretch}{1.2}
    \setlength{\tabcolsep}{8pt}
    \begin{tabular}{lrrc}
        \toprule
        \textbf{Metric} & \textbf{No Memory} & \textbf{Full Memory} & \textbf{Ratio vs full} \\
        \midrule
        CL-F1            & --- & --- & --- \\
        Tokens / task    & --- & --- & --- \\
        \midrule
        \textbf{Mean (8 seq.)} & \textbf{---} & \textbf{---} & \textbf{---} \\
        \bottomrule
    \end{tabular}
\end{table}
```
**B. Wide, grouped table with subtotals + footnote (per-policy-by-sequence / cost breakdown):**
```latex
\begin{table}[htbp]
    \centering
    \caption{Grouped breakdown ... (eval context).\textsuperscript{*}}
    \label{tab:KEY}
    \resizebox{\textwidth}{!}{%
    \begin{tabular}{llrrr}
        \toprule
        \textbf{Group} & \textbf{Item} & \textbf{Col A} & \textbf{Col B (M)} & \textbf{Status} \\
        \midrule
        \textbf{Group 1} & item a & --- & --- & --- \\
                         & item b & --- & --- & --- \\
                         \cmidrule{2-5}
                         & \textbf{Group 1 Subtotal} & \textbf{---} & \textbf{---} & -- \\
        \midrule
        \textbf{Grand Total} & \textbf{All} & \textbf{---} & \textbf{---} & \textbf{---} \\
        \bottomrule
    \end{tabular}%
    }
    \vspace{0.2cm}
    \begin{minipage}{0.9\textwidth}\footnotesize
        \textsuperscript{*} Note: clarifying caveat (e.g.\ excluded arm64-unbuildable
        tasks, declared deviation) goes here, not in body text.
    \end{minipage}
\end{table}
```
Use `\resizebox{\textwidth}{!}{...}` **only** on genuinely wide (5+ col) tables — it scales the font too, so a 3-col table wrapped in it looks oversized. For super-headers spanning columns: first header row `& \multicolumn{N}{c}{Group} \\` then `\cmidrule{2-(N+1)}` before the real column names.

### 4.4 `[DO NOW]` Cross-cutting conventions (apply to all tables)
- **Alignment**: text `l`, numeric `r` (decimals align), categorical/short `c`.
- **Units in the header** (`Latency (ms)`, `Result (\%)`), never repeated per cell.
- **Caption ABOVE the tabular**, one descriptive sentence ending with eval context; `\label{tab:...}` immediately after.
- **Float spec `[htbp]`, `\centering` first.**
- **Footnoted caveats** via `\textsuperscript{*}` + `minipage`, not body text — e.g. the CL-F1≡resolve-rate proxy caveat belongs in a table footnote.

### 4.5 `[WHEN-144-LANDS]` Convert numeric `r` columns to `siunitx` `S`-columns
When the H1 table fills, swap `{lrrrrlc}` to decimal-aligned `S`-columns so numbers don't ragged-align:
```latex
\begin{tabular}{l S[table-format=2.0] S[table-format=1.3]
                  S[table-format=1.3] S[table-format=-1.2] l c}
```
Wrap any remaining `---` placeholder as `{---}` so `siunitx` leaves it alone. Add the **Mean over 8 sequences** row bolded end-to-end and set off by `\midrule`. **Never invent the cell values** — fill only from `results/`.

---

## 5. Math / display-equation polish

Hard fact: **every file in `Chapter_4-Methodology/` has zero numbered `equation`/`align`** — the only display math is one unnumbered `\[...\]` in `4.2.5`. These are *definitions and frozen rules*, derivable now with zero results.

### 5.1 `[DO NOW]` Preamble — enable the notation the example uses
`preamble.tex` loads `amsmath` only (no `amssymb`, no `mathtools`):
```latex
\usepackage{amssymb}    % \mathbb (indicator \mathbb{I}, \mathbb{R}, \mathbb{N})
\usepackage{mathtools}  % better cases, \coloneqq
```

### 5.2 `[DO NOW]` Renumber + relabel + gloss the Type-Aware Decay equation (Invariant #8)
`Chapter_4-Methodology/4.2_Six-Memory-Policies/4.2.5_Type-Aware-Decay.tex` — replace the unnumbered `\[...\]`:
```latex
The score is the multiplicative Anderson--Schooler form~\cite{anderson1991}
(Invariant~\#8):
\begin{equation}
  \label{eq:type-decay}
  s(m) = b \cdot t^{-d(\tau)} \cdot \left(1 + r\right)^{1/2},
\end{equation}
where $s(m)$ is the retention score of memory record $m$, $b$ its base activation,
$t$ its age (tasks since insertion), $r$ its cumulative retrieval count, and
$d(\tau)\!>\!0$ the decay exponent keyed to the record's type
$\tau \in \{\texttt{architectural}, \texttt{api\_change}, \texttt{bug\_fix},
\texttt{test\_update}, \texttt{config}\}$ (Invariant~\#7). Age drives the score down,
retrieval lifts it back up with diminishing returns, and the per-type exponent sets
how fast each kind of record fades.
```
Then reference it elsewhere as `Eq.~\ref{eq:type-decay}`. This is the single highest polish-per-edit change: it turns the signature formula from a code-like aside into a citable law.

### 5.3 `[DO NOW]` Add the cosine retrieval equation (Invariant #5)
`Chapter_4-Methodology/4.4_Retrieval-Fixed-Invariant.tex` — formalize the central control:
```latex
Retrieval scoring is pure cosine similarity, identical across all six conditions:
\begin{equation}
  \label{eq:cosine}
  \operatorname{sim}(q, m) = \frac{\mathbf{e}_q \cdot \mathbf{e}_m}
                                  {\lVert \mathbf{e}_q \rVert \, \lVert \mathbf{e}_m \rVert},
\end{equation}
where $\mathbf{e}_q$ and $\mathbf{e}_m$ are the embeddings of the query and a stored
record. Each query returns the top $k = 5$ same-repository records by
$\operatorname{sim}(\cdot,\cdot)$ (Invariants~\#5,~\#16); no policy-specific bonus or
penalty enters the score.
```

### 5.4 `[DO NOW]` Number the metric *definitions* (not results) — `4.6_Metrics-and-Statistical-Plan.tex`
These are formulas; results stay in Chapter 5.
```latex
Memory lift quantifies interdependence (E7) as the gap between full and no-memory
resolution on sequence $j$:
\begin{equation}
  \label{eq:memory-lift}
  \Delta_j = \operatorname{res}_{\text{full}}(j) - \operatorname{res}_{\text{none}}(j).
\end{equation}
```

### 5.5 `[DO NOW]` Notation discipline + the equation sandwich (apply throughout Ch. 4)
- **Equation sandwich**: lead-in ending in colon → numbered display → `where …` gloss defining every symbol. No bare symbol left undefined.
- **Multi-letter operators** with `\operatorname{}` (upright): `\operatorname{softmax}`, `\operatorname{argmax}`, never italic `softmax`.
- **Vectors/matrices bold** (`\mathbf{e}`), **sets/spaces** `\mathcal{}`/`\mathbb{}`, **descriptive subscripts in `\text{}`** (`\lambda_{\text{lm}}`).
- **Borrowed formulas carry a `\cite`** at the point of definition.
- **Keep all six policies' notation consistent** (same `t`, `\tau`, `s`) so the policy ladder reads as one family.

### 5.6 `[DO NOW, optional]` One-line eviction equation per policy
Give `4.2.3` (Random), `4.2.4` (Recency), `4.2.6` (CLS) each a short numbered `equation` for its eviction criterion, so all six policies share a uniform mathematical face.

> **What NOT to do:** do not add equations to fill the *result* placeholder boxes. Those gaps are result tables/figures, not missing definitions.

---

## 6. Placeholder hygiene — make "pending" deliberate (`[DO NOW]`)

Bare `---` cells and three competing pending styles (yellow box / blue box / raw `[RESULT:]` / `---`) are what make the draft read as broken rather than staged.

### 6.1 Unify on one pending badge — `preamble.tex`
```latex
\usepackage{xcolor}
\newcommand{\pending}{\textit{\textcolor{gray}{pending}}}
% in tables, replace bare "---" with \pending (or keep --- but make it consistent)
```
Pick **one** visual language for the three pending kinds:
- Narrative pending → keep `todobox` (one color).
- Pending figure → keep `figurestub` (one color, excluded from LoF — correct).
- Pending number → `\pending` (or a typed `[RESULT: pending]` slot inside otherwise-finished prose).

Ensure the pending color is **distinct from the hyperref link color** (currently confusably close) so a reader doesn't read a pending badge as a link.

### 6.2 Keep the integrity headers
Standardize the `% INTEGRITY: every numeric value here is a PLACEHOLDER` comment at the top of each pending file. This is good practice — it makes intent auditable.

---

## 7. Writing-density habits (`[DO NOW]` where prose exists; templates `[WHEN-144-LANDS]`)

Our prose craft is already strong (Chapters 1–4 finished; instrument-validation section is a textbook table sandwich). The gaps are specific patterns to wire up so they auto-fill when results land — never with invented numbers.

1. **Table sandwich** — announce (`\ref` + what it contains) → float → read-back paragraph that re-quotes specific cells. Add a templated read-back paragraph under `tab:main-results` (5.2) with inline `[RESULT: pending]` slots so the *finished sentence shape* exists now.
2. **Enumerated structural read** — pre-commit a "First / Second / Third" shape per H-section, stating the *mechanism* now (mechanisms are design facts) and leaving only the magnitude pending.
3. **Roadmap sentence** atop each parent (Chapter 5 intro, §4.2.0) naming its children by content.
4. **Re-`\ref` floats in their analysis** — every table/figure referenced at least twice (announce + in-analysis). In 5.2, re-cite both Pareto figures in the synthesis paragraph.
5. **Delta/benefit column** in comparison tables so the comparison lives in the table, not only prose (the footprint story wants a `Ratio vs full` column — added in §4.3 template A).

---

## 8. Apply order & verification

**Lowest-risk-first batches** (recompile `pdflatex → bibtex → pdflatex ×2` after each):

1. **Front matter** (§2.1–2.2 title page, LoF/LoT) — pure additions.
2. **Figures** (§3.1–3.3 swap PDF, crop, de-text) — the chrome removal.
3. **Placeholder hygiene** (§6) — unify pending language.
4. **Math** (§5.1–5.4 amssymb, decay eq, cosine eq, metric defs).
5. **Tables** (§4.2–4.4 packages + templates + conventions).
6. **Preamble polish** (§2.3–2.8 caption/fancyhdr/cleveref/titlesec/texttt/bib).
7. **Optional/high-polish**: §3.4 TikZ architecture, §5.6 per-policy eqs.
8. **`[WHEN-144-LANDS]`**: §3.5 subfigure plots, §4.5 siunitx S-columns, §7 read-back fills — structural only, values from `results/` exclusively.

**Verify before declaring done:** confirm no `caption`/`hyperref`/`cleveref` load-order warnings, no `siunitx`-vs-`---` complaints, and that LoF/LoT populate from real captions only.

---

## 9. Key file targets (absolute paths)

- Front matter / preamble: `paper/latex/main.tex`, `paper/latex/preamble.tex`
- Figures: `paper/latex/Chapter_4-Methodology/4.1_Controlled-Comparison-Design.tex` (~line 44), `paper/latex/Chapter_4-Methodology/4.2_Six-Memory-Policies/4.2.0_Overview.tex` (~line 56), `paper/latex/figures/architecture.pdf`, `paper/latex/figures/task-lifecycle.pdf`
- Math: `paper/latex/Chapter_4-Methodology/4.2_Six-Memory-Policies/4.2.5_Type-Aware-Decay.tex` (lines 13–16), `paper/latex/Chapter_4-Methodology/4.4_Retrieval-Fixed-Invariant.tex`, `paper/latex/Chapter_4-Methodology/4.6_Metrics-and-Statistical-Plan.tex`
- Tables / writing: `paper/latex/Chapter_5-Results/5.0_Instrument-Validation.tex`, `5.1_Setup-and-Descriptives.tex` (~line 49), `5.2_H1-NonInferiority-and-Pareto.tex` (~line 38)
- Example exemplars: `example_contents/Chapter_4-Methodology/4.1_Architecture-Overview/4.1_Architecture-Overview.tex`, `.../4.6_Multi-Task_Loss/4.6_Multi-Task_Loss.tex`, `example_contents/Chapter_5-Experiments/5.2_Evaluation-Metrics/5.2_Evaluation_Metrics.tex`, `.../5.3_Training-Strategy/5.3.5_Stage2.tex`, `.../5.4_Results/{5.4.1,5.4.3,5.4.6}*.tex`

---

> **In one line:** Ours looks unfinished because it is a staged draft with tool-chrome figures and bare placeholders — not because of typography. Fill the title page + lists, swap to cropped vector PDFs, make "pending" deliberate, and promote the two signature equations to numbered display math; that closes most of the gap with zero fabricated numbers.
