# OURS-AUDIT — Presentation audit of the LaTeX report

Scope: `paper/latex/` on branch `rerun/instrument-fix`. This audits **presentation craft only**, not content. The report is an honest progressive draft: results-bearing cells are intentionally placeholders pending the 144 rerun. Nothing below recommends fabricating results. The gap vs `example_contents` is NOT typography (both use Computer Modern) — it is (1) the visible density of placeholder scaffolding and (2) a handful of figure/table/front-matter craft items that we can fix now.

---

## (a) Placeholder scaffolding — the dominant "unfinished" signal

Three placeholder devices are defined in `preamble.tex`:
- `todobox` (yellow `tcolorbox`, lines 26–37) — prose TODO callouts
- `figurestub` (blue `tcolorbox`, lines 39–47) — pending figures
- literal `---` table cells + `[RESULT: pending runs\_144\_seq\_cceb325]` inline markers — pending numbers

### Counts (exact, from grep)
| Device | Total | Files |
|---|---|---|
| `\begin{todobox}` | **11** | 11 files (1 each) |
| `\begin{figurestub}` | **3** | 2 files |
| `[RESULT: pending]` inline markers | **18** | 6 files |
| Tables with `---` placeholder cells | 2 tables | `5.1`, `5.2` |

### `todobox` locations (11)
- `Appendix/A_Reproducibility-and-Provenance.tex`
- `Appendix/B_Extended-Results.tex`
- `Chapter_5-Results/5.3_H2-Content-vs-Random.tex`
- `Chapter_5-Results/5.4_H3-CLS-Consolidation.tex`
- `Chapter_5-Results/5.5_H4-Behavioral.tex`
- `Chapter_5-Results/5.6_H5-and-Interdependence.tex`
- `Chapter_5-Results/5.7_Manipulation-Checks.tex`
- `Chapter_6-Discussion/6.1_Key-Findings.tex`
- `Chapter_6-Discussion/6.2_Implications.tex`
- `Chapter_7-Conclusion/7.1_Conclusion.tex`
- `Chapter_7-Conclusion/7.2_Future-Work.tex`

### `figurestub` locations (3)
- `Chapter_4-Methodology/4.5_Agent-Benchmark-and-Model.tex:1`
- `Chapter_5-Results/5.2_H1-NonInferiority-and-Pareto.tex:2` (the two Pareto plots, lines 85–108)

### `[RESULT: pending]` markers by file
- `Chapter_5-Results/5.2_H1-NonInferiority-and-Pareto.tex` — 9
- `Chapter_5-Results/5.1_Setup-and-Descriptives.tex` — 3
- `Chapter_4-Methodology/4.5_Agent-Benchmark-and-Model.tex` — 2
- `Abstract/Abstract.tex` — 2
- `Chapter_4-Methodology/4.2_Six-Memory-Policies/4.2.6_CLS-Consolidation.tex` — 1
- `Chapter_1-Introduction/1.4_Contributions.tex` — 1

### `---` placeholder tables
- `5.1_Setup-and-Descriptives.tex:49–62` — `tab:descriptives`, 6 policies × 5 metric cols, every data cell `---`
- `5.2_H1-NonInferiority-and-Pareto.tex:38–48` — `tab:main-results`, 5 contrasts × 6 cols, every data cell `---`

**Assessment.** The scaffolding is concentrated: the entire Results chapter (5.1–5.7), all of Discussion 6.1–6.2, both Conclusion sections, and both appendices read as "boxes". This is honest and correct for a pre-results draft, but it is the single biggest reason the document scans as unfinished. Chapters 1–4 (Intro, Background, Related Work, most of Methodology) are largely finished prose and read fine.

### Craft fixes available NOW (no fabrication)
1. **The `---` em-dash cells look like errors, not "pending."** A bare `---` reads as a typesetting mistake to an examiner. Make "pending" explicit and visually intentional. Replace each placeholder cell body with a faint, uniform token:
   ```latex
   % preamble.tex
   \newcommand{\pend}{\textcolor{pendingline}{\textendash\textendash}}
   ```
   then use `\pend` in the cells. Or, cleaner for a whole pending table, overlay one diagonal "pending" watermark band instead of 30 dashes — keeps the column structure visible (so the reader sees what *will* be reported) without 30 repeated dashes screaming "empty":
   ```latex
   \begin{table}[htbp]\centering
   \caption{...}\label{tab:main-results}
   \begin{tabular}{lrrrrlc}\toprule
   Contrast (vs \texttt{full\_memory}) & $W$ & $p$ & Holm $p$ & $r_{rb}$ & 95\% BCa CI & Sig. \\ \midrule
   \multicolumn{7}{c}{\itshape\color{pendingtext} values pending the trustworthy 144 rerun (runs\_144\_seq\_cceb325)}\\
   \midrule
   random\_prune & & & & & & \\
   recency\_prune & & & & & & \\
   ... \bottomrule
   \end{tabular}\end{table}
   ```
2. **Unify the "pending" vocabulary.** Right now three different visual languages signal the same state (yellow box / blue box / inline `\texttt{[RESULT: pending ...]}` / bare `---`). Pick a deliberate palette: blue `figurestub` for figures, blue inline badge for numbers, yellow `todobox` only for *prose to be written*. Add one inline badge command so the 18 `[RESULT: pending]` strings stop looking like raw code:
   ```latex
   \newtcbox{\pendingbadge}{on line, boxsep=1pt, left=3pt, right=3pt, top=1pt, bottom=1pt,
     colframe=pendingline, colback=pendingfill, coltext=pendingtext, boxrule=0.4pt, arc=2pt,
     fontupper=\footnotesize\sffamily}
   % usage: \pendingbadge{pending: runs\_144\_seq\_cceb325}
   ```
3. **`todobox` `before upper` hard-codes "TODO ·".** Fine, but consider a count/anchor so the draft is self-tracking, e.g. a `\todobox` that also writes to a `\listoftodos`-style list, letting you (and an examiner) see a clean "N open items" page rather than discovering boxes mid-read.

---

## (b) Real figures — quality issues

Two real images, both Archify-exported diagrams (good content, not "cramped screenshots" of code/terminals — that fear is unfounded). Files in `figures/`:
- `architecture.png` (156 KB, 1456×~648) — referenced `4.1_Controlled-Comparison-Design.tex:44`
- `task-lifecycle.png` (131 KB, ~2160×1240) — referenced `4.2.0_Overview.tex:56`
- PDF twins also exist (`architecture.pdf`, `task-lifecycle.pdf`) — **prefer these** (see fix 3).

Both are embedded `\includegraphics[width=\textwidth]{...}`.

**Real quality problems (visible in the renders):**
1. **Tool chrome leaks into the figure.** Both PNGs carry an Archify footer: *"Architecture diagram • Built with Archify • Press T for theme and E for export"* and a *"● bullet"* title-marker dot. That UI text in a thesis figure is the actual amateur tell — far more than CM fonts. Crop it out.
2. **Huge dead margins / low ink density.** `task-lifecycle.png` is ~2160×1240 but the diagram occupies the center ~60%; the outer rounded "card" frame + grid background + bottom legend cards eat space. At `\textwidth` the actual node labels shrink to near-illegible (e.g. "identical across policies", "the policy forgets here" are tiny). `architecture.png` has the same low-density problem horizontally.
3. **Label text is too small at print size.** Because the canvas is mostly whitespace, the meaningful text renders small once scaled to column width. This is the "cramped" feeling — not a screenshot, but under-cropped vector art downscaled too far.

**Fixes (now):**
- **Re-export cropped and tight.** In Archify, export without the footer/title-dot and with minimal canvas padding. If re-export isn't convenient, crop the existing PDF (vector, lossless):
  ```bash
  # pdfcrop ships with TeX Live; trims whitespace + the footer if you nudge margins
  pdfcrop --margins '2 2 2 2' figures/architecture.pdf figures/architecture-crop.pdf
  pdfcrop --margins '2 2 2 2' figures/task-lifecycle.pdf figures/task-lifecycle-crop.pdf
  ```
  (The footer line will need a manual bottom crop, e.g. `--bbox` or a one-off in Preview, since pdfcrop keeps it as content.)
- **Embed the PDF, not the PNG**, so labels stay sharp at any size:
  ```latex
  \includegraphics[width=\textwidth]{architecture-crop.pdf}
  ```
- **task-lifecycle is portrait-ish and label-dense** — give it more vertical room and don't force full text width if that shrinks labels. Consider `width=0.85\textwidth` after cropping, or rotate to a `sidewaystable`/`\begin{figure}` landscape page if it stays wide.
- **Light-theme is correct for print** (both are already light) — keep it; do not export the dark theme.

---

## (c) Table styling

Six real tables, all plain `booktabs` (`\toprule/\midrule/\bottomrule`), no `resizebox`, no `tabularx`, no `siunitx`, no `threeparttable`, no `\caption` package. Locations:
- `4.2.0_Overview.tex:34` — `tab:policies` (`lll`)
- `4.6_Metrics-and-Statistical-Plan.tex:52` — metrics (`lll`)
- `5.0_Instrument-Validation.tex:33` — instrument gate (`lrr`, uses `\multicolumn`)
- `5.1_Setup-and-Descriptives.tex:42` — `tab:descriptives` (`lrrrrr`, all `---`)
- `5.2_H1-...tex:31` — `tab:main-results` (`lrrrrlc`, all `---`)
- `6.3_Deviations-from-Preregistration.tex:80` — deviations (`lll`)

**What's fine.** booktabs is the right base; no vertical rules; captions above tables (book convention) — all correct and matches `example_contents`' restraint.

**What's rough / fixable now:**
1. **No numeric column alignment.** The two results tables (`lrrrrr`, `lrrrrlc`) will hold decimals once filled; right-aligned `r` columns do *not* decimal-align (`0.29` vs `0.3` won't line up). Add `siunitx` and use `S` columns so numbers align on the decimal and carry uncertainty cleanly:
   ```latex
   \usepackage{siunitx}
   \sisetup{table-format=1.3, detect-weight, mode=text}
   % column spec: l S S S S S c   ;  header cells wrapped in {...}
   ```
   This is the single highest-leverage table change for when results land.
2. **No width guard.** `5.2`'s 7-column table can overflow `\textwidth` once the "95% BCa CI" column holds `[-0.12, 0.34]` strings. Wrap wide tables so they never bleed into the margin:
   ```latex
   \usepackage{adjustbox}        % or threeparttable + small
   \begin{adjustbox}{max width=\textwidth}
     \begin{tabular}{...}...\end{tabular}
   \end{adjustbox}
   ```
   (Prefer `adjustbox`/`max width` over `\resizebox{\textwidth}` — the latter scales fonts and produces inconsistent type sizes across tables.)
3. **Two-line stacked headers done by hand** (`5.1` puts units on a second `&`-row, lines 51–52). Works, but `makecell` gives cleaner control:
   ```latex
   \usepackage{makecell}
   \newcommand{\hd}[2]{\thead{#1\\\footnotesize #2}}
   ```
4. **Footnotes/units belong in the table, not the caption.** `5.1`/`5.2` captions carry "Footprint is memory tokens carried per task; total cost is tokens per run." Move unit defs into a `threeparttable` note so captions stay short:
   ```latex
   \usepackage{threeparttable}
   \begin{threeparttable}...\begin{tablenotes}\footnotesize
     \item Footprint = memory tokens/task; total cost = tokens/run.
   \end{tablenotes}\end{threeparttable}
   ```
5. **No `caption` package** → caption font = body font, label not bold. Minor, but `\usepackage[font=small,labelfont=bf]{caption}` makes figure/table captions read as captions (matches polished theses) without touching CM body type.

---

## (d) Title page & front matter — currently bare

`main.tex:13–23` is a hand-rolled `titlepage`: title + subtitle + "Master's Thesis", nothing else. **Issues:**
- `\author{}` is **empty** (`main.tex:7`) — no name on the title page at all.
- No university, department, degree program, supervisor/examiner, submission date, city, or logo. `example_contents` (a finished thesis) almost certainly has these; their absence is a strong "draft" signal independent of results.
- `\date{Master's Thesis}` misuses `\date` as a label.
- **No `\listoffigures` / `\listoftables`** despite having real figures and many tables — a finished thesis has both after the ToC.
- No acknowledgements, no declaration/statement of authorship (standard in master's theses), no abstract *page* styling (abstract is a `\chapter*` only).
- ToC is bare `\tableofcontents` with default depth — fine, but with the placeholder sections it will list "Results" subsections that are stubs.

**Fixes (now — these are content-free and high-impact):**
```latex
% main.tex titlepage — fill institutional block
{\Large\bfseries Memory Pruning and Forgetting Policies\\ for AI Coding Agents\par}
\vspace{0.6em}{\large Impact on Performance Across Sequential Tasks\par}
\vspace{2cm}
{\large Author Name\par}\vspace{0.4em}
{\normalsize A thesis submitted for the degree of\\ Master of \dots\par}
\vspace{1.5cm}
{\normalsize Department \dots\\ University \dots\par}
\vfill {\normalsize \monthname\ \the\year\par}
```
```latex
% main.tex after \tableofcontents
\listoffigures
\listoftables
```
Add a `\chapter*{Acknowledgements}` and a `\chapter*{Statement of Authorship}` stub in front matter (these are expected, not results). Set ToC depth explicitly so the 4.2.x policy sub-subsections don't bloat it:
```latex
\setcounter{tocdepth}{2}
```

---

## (e) Other visually rough / loose ends

1. **`\linespread{1.08}` + `\parskip 0.25em` + `\parindent 1.5em`** (`preamble.tex:49–51`): mixing paragraph indent *and* paragraph skip is the classic LaTeX double-cue. Pick one. For a CM book the cleaner look is indented paragraphs with **no** extra `\parskip`:
   ```latex
   \setlength{\parindent}{1.5em}\setlength{\parskip}{0pt}\linespread{1.05}
   ```
2. **`oneside` book** (`main.tex:1`): fine for screen/PDF submission; if the program wants printed/bound, switch to `twoside` for proper margin mirroring — decide deliberately.
3. **`\nocite{*}`** (`main.tex:87`) dumps the *entire* `references.bib` into the bibliography whether cited or not — a finished thesis cites deliberately. Remove `\nocite{*}` before submission so the reference list reflects actual citations. (`references.bib` exists, 6.2 KB.)
4. **`bibliographystyle{plain}`** gives numeric `[1]` unsorted-by-appearance + no DOIs/URLs. For a CS thesis consider `plainnat`+`natbib` or `IEEEtran`/`alpha`; `plain` is the bare default and reads as such.
5. **`hyperref` link colors** are all set to `pendingtext` (blue) (`preamble.tex:18–24`) — that's the same blue as the "pending" UI, so real cross-reference links and "pending" badges share a color and can be confused. Give links a distinct, soberer color (or `hidelinks` / black for print) so the pending-blue stays meaningful.
6. **No `cleveref`** — refs are hand-typed "Figure~\ref{}", "Table~\ref{}", "Section~\ref{}". Works, but `cleveref` (`\cref`) prevents "Figure~5" vs "figure 5" inconsistencies across the long doc.
7. **No `\usepackage{float}` / `[H]`** — all floats are `[htbp]`; once the doc fills, placeholder figures may drift far from their text. Not urgent now.
8. **Generated-file header comments** (`% Generated from the matching Typst scaffold by scripts/migrate_typst_report_to_latex.py`) are in many `.tex` files — harmless (comments), but worth a note that the LaTeX is downstream of Typst; edits here can be overwritten by a re-run of the migration script.

---

## Priority order (presentation, do-now, no fabrication)
1. **Crop the two figures + drop the Archify footer; embed the PDFs** (biggest "amateur → finished" jump). (b)
2. **Fill the title page institutional block + add `\listoffigures`/`\listoftables` + authorship/acknowledgements stubs.** (d)
3. **Make "pending" deliberate**: replace bare `---` with an intentional pending row/badge; unify the three pending visual languages. (a)
4. **Add `siunitx` + `adjustbox` table scaffolding now** so results tables decimal-align and never overflow when numbers land. (c)
5. **Tidy `\parskip`/`parindent`, link colors, drop `\nocite{*}`, pick a real bib style.** (e)

## Files to touch
- `paper/latex/preamble.tex` — packages (`siunitx`, `adjustbox`, `caption`, `makecell`, `threeparttable`, `cleveref`), pending-badge/`\pend` commands, paragraph + link-color settings, bib style.
- `paper/latex/main.tex` — title page block, `\author`, `\listoffigures`/`\listoftables`, `tocdepth`, remove `\nocite{*}`.
- `paper/latex/figures/` — re-export/crop `architecture.*`, `task-lifecycle.*`; switch refs to cropped PDFs in `4.1_Controlled-Comparison-Design.tex:44` and `4.2.0_Overview.tex:56`.
- Results tables: `5.1_Setup-and-Descriptives.tex`, `5.2_H1-NonInferiority-and-Pareto.tex` (pending-row + `S` columns + `adjustbox`).
