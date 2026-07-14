# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A complete, unabridged parallel German/English translation of Karl Kautsky's *Das Erfurter Programm* (1892), published as a bilingual Quarto website. `Plan.md` documents the full design and its rationale — read it before changing pipeline behaviour.

## Commands

```
make venv        # one-time: create .venv and install deps
make scrape      # cache the 7 MIA source pages into data/raw_html/
make segment     # raw_html → data/blocks.jsonl (preserves existing translations)
make translate   # fill en_html via Anthropic API; needs ANTHROPIC_API_KEY; resumable
make qa          # deterministic checks; flags problem blocks in place
make site        # blocks.jsonl → site/chapters/*.qmd
make render      # quarto render site/  (output in site/_site/)
make epub        # blocks.jsonl → book/chapters/*.qmd, then quarto render book/
                 # (English-only EPUB in book/_book/)
```

Scripts run directly with `.venv/bin/python`. Translate accepts chapter IDs to restrict a run: `.venv/bin/python pipeline/03_translate.py ch1 ch2`. Preview locally with `quarto preview site/`. There are no tests or linters.

Pushing to `main` triggers `.github/workflows/publish.yml`, which renders and publishes the site to GitHub Pages.

## Architecture

**`data/blocks.jsonl` is the single source of truth.** One JSON object per line, one line per translation block:

```json
{"id": "ch1-3f9a02c1", "chapter": "ch1", "type": "paragraph|heading|blockquote|table|list|footnote",
 "de_html": "...", "de_text": "...", "en_html": null,
 "status": "untranslated|translated|flagged|verified", "qa": []}
```

The pipeline stages (`pipeline/01_…05_*.py`, shared constants and atomic block I/O in `pipeline/common.py`) all read and write this file:

- **Block IDs are content hashes** (`{chapter}-{sha1(de_text)[:8]}`), not positions — re-running `02_segment.py` after a segmenter fix carries existing translations over by ID instead of orphaning them.
- **03_translate** batches blocks into heading-bounded sections (~15 blocks / ~8K chars), sends the full German chapter as a cached system block, and uses structured outputs (JSON schema) to get one `en_html` per block ID. Model is `claude-opus-4-8`; do not pass `temperature` (rejected by current Opus models). Progress saves after every section, so interrupted runs resume; failed sections are retried simply by re-running.
- **04_qa_check** runs three deterministic checks (en/de length ratio, inline-tag multiset parity, glossary term presence/avoidance) and sets `status` to `flagged` with reasons in `qa`. Blocks marked `verified` are never touched — that status is the human sign-off, set by hand-editing `blocks.jsonl`.
- **05_generate_qmd** renders CSS-grid parallel columns (German left, English right), headings as real Markdown headings for the TOC, tables full-width, and footnotes in a bilingual end section with anchors remapped to chapter-unique IDs. Block HTML is emitted through `{=html}` raw blocks — without them pandoc re-parses the content as markdown and breaks the `:::` fences.

- **06_generate_epub** writes English-only chapters to `book/chapters/*.qmd` for the Quarto *book* project in `book/` (a separate project because only book projects can emit EPUB). `book/_quarto.yml` (chapter list, metadata) and `book/index.qmd` (about page) are maintained by hand.

**`site/chapters/*.qmd` and `book/chapters/*.qmd` are generated files — never hand-edit them.** Corrections go into `blocks.jsonl` (by block ID, flipping `status` to `verified`), then `make site render` / `make epub`.

The sidebar in `site/_quarto.yml` (chapter and subsection links) is maintained by hand; if headings change, its anchor hrefs must be updated to match the slugs Quarto generates.

## Translation conventions

`data/glossary.yaml` is the termbase contract (e.g. *Arbeitskraft* → labour-power, *Mehrwert* → surplus value); German stems match as lowercase substrings so compounds are caught, and QA enforces entries mechanically. British spelling throughout. Completeness is the highest priority — the existing Bohn translation's abridgement is the failure mode this project exists to fix, so never merge, drop, or summarize clauses when editing translations.
