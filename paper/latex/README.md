# Thesis Report - LaTeX source

This directory is the LaTeX migration of the canonical Typst scaffold in
`paper/report/`. It preserves the modular section layout, comments, TODO guidance,
result placeholders, and bibliography keys without inventing prose or results.

## Build

From the repository root:

```bash
python3 /Users/leodinh/.codex/plugins/cache/openai-bundled/latex/0.2.2/scripts/compile_latex.py \
  /Users/leodinh/Documents/personal/thesis/paper/latex/main.tex \
  --compiler tectonic \
  --output-directory /Users/leodinh/Documents/personal/thesis/paper/latex/build
```

The bundled Tectonic runtime performs the required LaTeX and BibTeX passes.

## Regenerate section files

The section files are mechanically generated from `paper/report/**/*.typ`:

```bash
python3 scripts/migrate_typst_report_to_latex.py
```

`main.tex`, `preamble.tex`, `references.bib`, and this README are maintained as
LaTeX-specific files. Do not fabricate result values or add unverified citations.
