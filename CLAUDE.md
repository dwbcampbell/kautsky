# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Complete, unabridged parallel German/English translations of works of German Marxists (source: marxists.org), published as a combined bilingual Quarto website with one section per work. `Plan.md` documents the pipeline design and its rationale plus the multi-work structure — read it before changing pipeline behaviour. The first work is Karl Kautsky's *Das Erfurter Programm* (1892).

## Commands

All pipeline targets operate on one work, selected with `WORK` (default `erfurter-programm`):

```
make venv        # one-time: create .venv and install deps
make scrape      # cache the MIA source pages into works/$(WORK)/data/raw_html/
make segment     # raw_html → works/$(WORK)/data/blocks.jsonl (preserves existing translations)
make translate   # fill en_html via Anthropic API; needs ANTHROPIC_API_KEY; resumable
                 # restrict to chapters with CHAPTERS="ch1 ch2"
make qa          # deterministic checks; flags problem blocks in place
make site        # blocks.jsonl → site/$(WORK)/chapters/*.qmd
make render      # quarto render site/  (output in site/_site/)
make epub        # blocks.jsonl → works/$(WORK)/book/chapters/*.qmd, then quarto render
                 # (English-only EPUB in works/$(WORK)/book/_book/)
```

Scripts run directly with `.venv/bin/python`; every script takes the work slug as its first positional argument, e.g. `.venv/bin/python pipeline/03_translate.py erfurter-programm ch1 ch2`. An unknown slug exits with the list of available slugs. Preview locally with `quarto preview site/`. There are no tests or linters.

Pushing to `main` triggers `.github/workflows/publish.yml`, which renders and publishes the site to GitHub Pages.

## Architecture

Each work lives in `works/<slug>/`: a `work.yaml` manifest (author, titles, year, MIA base URL, masthead headings to drop, translation-prompt text, `legacy_url_prefix`, chapter list), its `data/` (raw HTML cache + blocks.jsonl), and its `book/` Quarto book project for the EPUB. `pipeline/common.py` parses the manifest into frozen `Work`/`Chapter` dataclasses that carry all derived paths; `parse_work_arg()` is the entry point every script uses.

**`works/<slug>/data/blocks.jsonl` is the single source of truth per work.** One JSON object per line, one line per translation block:

```json
{"id": "ch1-3f9a02c1", "chapter": "ch1", "type": "paragraph|heading|blockquote|table|list|footnote",
 "de_html": "...", "de_text": "...", "en_html": null,
 "status": "untranslated|translated|flagged|verified", "qa": []}
```

The pipeline stages (`pipeline/01_…06_*.py`, shared manifest loading and atomic block I/O in `pipeline/common.py`) all read and write this file:

- **Block IDs are content hashes** (`{chapter}-{sha1(de_text)[:8]}`), not positions — re-running `02_segment.py` after a segmenter fix carries existing translations over by ID instead of orphaning them.
- **03_translate** batches blocks into heading-bounded sections (~15 blocks / ~8K chars), sends the full German chapter as a cached system block, and uses structured outputs (JSON schema) to get one `en_html` per block ID. The system prompt's work-specific sentences come from `work.yaml` (`translation.description`, `translation.completeness_note`). Model is `claude-opus-4-8`; do not pass `temperature` (rejected by current Opus models). Progress saves after every section, so interrupted runs resume; failed sections are retried simply by re-running.
- **04_qa_check** runs three deterministic checks (en/de length ratio, inline-tag multiset parity, glossary term presence/avoidance) and sets `status` to `flagged` with reasons in `qa`. Blocks marked `verified` are never touched — that status is the human sign-off, set by hand-editing `blocks.jsonl`.
- **05_generate_qmd** renders CSS-grid parallel columns (German left, English right), headings as real Markdown headings for the TOC, tables full-width, and footnotes in a bilingual end section with anchors remapped to chapter-unique IDs. Block HTML is emitted through `{=html}` raw blocks — without them pandoc re-parses the content as markdown and breaks the `:::` fences. When the manifest sets `legacy_url_prefix`, each chapter gets an `aliases:` frontmatter entry so pre-restructure URLs redirect.
- **06_generate_epub** writes English-only chapters to `works/<slug>/book/chapters/*.qmd` for the Quarto *book* project (a separate project because only book projects can emit EPUB). `book/_quarto.yml` (chapter list, metadata) and `book/index.qmd` (about page) are maintained by hand.

**`site/<slug>/chapters/*.qmd` and `works/<slug>/book/chapters/*.qmd` are generated files — never hand-edit them.** Corrections go into `blocks.jsonl` (by block ID, flipping `status` to `verified`), then `make site render` / `make epub`.

The site is one combined Quarto website. `site/index.qmd` (hand-maintained, `sidebar: false`) lists all works grouped by author. `site/_quarto.yml` holds one **named sidebar per work** (`- id: <slug>`) whose hrefs are prefixed with the work slug; the sidebar's chapter and subsection links are maintained by hand, so if headings change, its anchor hrefs must be updated to match the slugs Quarto generates. Adding a work is purely additive — see the Milestone 2 recipe in `Plan.md`.

## Translation conventions

`shared/glossary.yaml` is the common termbase contract (e.g. *Arbeitskraft* → labour-power, *Mehrwert* → surplus value); German stems match as lowercase substrings so compounds are caught, and QA enforces entries mechanically. A work may extend it with `works/<slug>/data/glossary.yaml`: per-work entries replace shared entries with overlapping German stems, otherwise they are appended (`common.load_glossary` prints a merge summary). British spelling throughout. Completeness is the highest priority — abridgement (as in the Bohn Kautsky translation) is the failure mode this project exists to fix, so never merge, drop, or summarize clauses when editing translations.
