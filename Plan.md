# Kautsky *Erfurter Programm* — Parallel Translation Project

Produce a complete, unabridged, terminologically consistent English translation of Karl
Kautsky's *Das Erfurter Programm in seinem grundsätzlichen Theil erläutert* (1892), and
publish it as a bilingual parallel-column website built with Quarto.

**Why:** the standard English translation (William E. Bohn, *The Class Struggle*, 1910)
compresses the German text to roughly two-thirds of its length — omitting illustrative
passages, statistical tables, and nuance — and renders core terminology inconsistently.

*This document records the original single-work design; its rationale still governs the
pipeline. The repo has since been restructured to host several works — see
[Multi-work structure](#multi-work-structure) at the end for the current layout and the
recipe for adding a work.*

## Source

German text on the Marxists Internet Archive (based on the Dietz Verlag, Berlin 1965
edition). Verified page inventory:

| File | Content |
|---|---|
| `vorwort-92.htm` | Vorwort zur ersten Auflage (1892) |
| `vorwort-04.htm` | Vorrede zur fünften Auflage (1904) |
| `1-untergang.htm` | I. Der Untergang des Kleinbetriebes |
| `2-proletariat.htm` | II. Das Proletariat |
| `3-kapitalisten.htm` | III. Die Kapitalistenklasse |
| `4-zukunftsstaat.htm` | IV. Der Zukunftsstaat |
| `5-klassenkampf.htm` | V. Der Klassenkampf |

Base URL: `https://www.marxists.org/deutsch/archiv/kautsky/1892/erfurter/`

The German text is public domain (Kautsky died 1938). The new translation is our
copyright; state a license (e.g. CC BY-SA) in `site/erfurter-programm/editorial.qmd`.

## Pipeline

```
[ MIA German HTML ] ─► 01_scrape ──► works/<slug>/data/raw_html/    (cached, one-time)
                       02_segment ─► works/<slug>/data/blocks.jsonl (one block per line — SOURCE OF TRUTH)
                       03_translate ► en_html filled in-place       (Anthropic API, resumable)
                       04_qa_check ─► blocks flagged in-place       (deterministic checks first)
                       05_generate ─► site/<slug>/chapters/*.qmd
                       quarto render site/ ─► parallel bilingual website
```

A single file per work, `works/<slug>/data/blocks.jsonl`, is the source of truth. Each
line is one block:

```json
{"id": "ch1-3f9a02c1", "chapter": "ch1", "type": "paragraph|heading|blockquote|table|list|footnote",
 "de_html": "<p>…</p>", "de_text": "…", "en_html": null,
 "status": "untranslated|translated|flagged|verified", "qa": []}
```

One line per block keeps git diffs reviewable; status transitions record progress.

## Key design decisions

1. **Stable block IDs.** IDs are `{chapter}-{sha1(de_text)[:8]}` (with a suffix on rare
   collisions), *not* positional indices — re-running the segmenter after a fix never
   orphans existing translations.

2. **Segmentation is structural, not char-based.** Top-level DOM blocks (`h1–h4`, `p`,
   `blockquote`, `table`, `ol/ul`) with ancestor filtering so nested elements aren't
   double-counted. Kautsky's statistical tables are kept as whole `table` blocks
   (layout/nav tables are distinguished from data tables and dropped). Footnotes are
   split into their own `footnote` blocks.

3. **Model: `claude-opus-4-8`.** (The originally proposed `claude-3-5-sonnet-20241022`
   was retired in Oct 2025.) No sampling parameters — `temperature` is rejected by
   current Opus models.

4. **Translate section-sized batches, not single paragraphs.** Blocks are grouped into
   heading-bounded batches (~15 blocks / ~8K chars). This gives real discourse context,
   cuts request count ~20×, and alignment is preserved because the model must return one
   entry per block ID.

5. **Full chapter as cached context.** The entire German chapter rides along as a
   system block with `cache_control: ephemeral`. Every request after the first per
   chapter reads it from cache at ~0.1× price, and the model always has complete
   antecedent context (fixes pronoun-reference drift, e.g. *er* → *it* for *der Staat*).

6. **Structured outputs, not free-form JSON.** `output_config.format` with a JSON
   schema guarantees a parseable `{id → en_html}` array — no `json.loads` roulette.

7. **Resumable by construction.** Progress is written back to `blocks.jsonl`
   (atomically) after every section; re-running skips anything already translated.

8. **QA is deterministic first, LLM second.** Cheap checks catch the real failure
   modes: length-ratio outliers (omission detector), inline-HTML tag parity between
   `de_html` and `en_html`, glossary-term presence / avoid-term absence (lowercase stem
   matching — catches compounds like *Arbeitskraftverkäufer* without spaCy). Only
   flagged blocks warrant an LLM critique pass (optionally via the Batches API at 50%
   cost).

9. **Human review happens in the browser.** Render the *draft* translation to the
   Quarto site early; review parallel text where it's readable; record corrections back
   into `blocks.jsonl` by block ID, flipping `status` to `verified`.

## Glossary (termbase)

`shared/glossary.yaml` — the contract that fixes Bohn's inconsistencies. Each entry:
German stems (matched as lowercase substrings, so compounds are caught), the required
English rendering, terms to avoid, and a note. Grow it as translation proceeds; QA
enforces it mechanically.

Anchor terms: *Arbeitskraft* → labour-power, *Mehrwert(h)* → surplus value,
*Klassenkampf* → class struggle, *Kleinbetrieb/Großbetrieb* → small-/large-scale
enterprise, *Lohnarbeit* → wage labour, *Genossenschaft* → cooperative,
*Warenproduktion* → commodity production. British spelling throughout.

## Translation prompt (system)

- Peer-reviewed scholarly translator persona; complete and unabridged — never merge,
  split, summarize, or omit a clause (the Bohn abridgement is the failure mode).
- Apply the glossary strictly.
- Preserve all inline HTML (`<em>`, `<a>`, footnote anchors) exactly.
- Tables: translate only header/word cells; never alter numeric data.
- Register: clear, readable academic English; British spellings.

## Edge cases

- **Footnotes:** extracted as `footnote` blocks; anchors remapped to globally unique
  IDs (`#n1` → `#ch2-n1`) at site-generation time; rendered bilingually below the
  parallel columns.
- **Headings:** rendered as real Markdown headings spanning both columns (tags stripped
  so the TOC stays clean), with the German original as a subtitle line.
- **Tables:** rendered full-width between the parallel columns (DE and EN versions
  stacked), inside an `overflow-x` container.
- **Images:** the segmenter skips image-only tables, so embedded diagrams (e.g. the
  two working-day GIFs in *Oekonomische Lehren* ab2-kap07) are hand-inserted
  `verified` blocks in blocks.jsonl, with `src="../assets/…"` resolving from both
  `site/<slug>/chapters/` and `book/chapters/`, and the files copied into
  `site/<slug>/assets/` and `works/<slug>/book/assets/`. **Re-running 02_segment
  drops these blocks — re-insert them after any re-segment.**

## Site

Quarto website; CSS grid parallel columns (`site/assets/parallel.css`), German left /
English right, stacking vertically on mobile. `css` and `page-layout` are set once in
`_quarto.yml`, not per-file. Deploy via GitHub Pages / Netlify.

## Cost estimate

~1,500 blocks, two passes, Opus 4.8 with chapter caching: on the order of **tens of
dollars** total. Not worth optimizing further.

## Workflow

```
make venv        # one-time: .venv + dependencies
make scrape      # cache the MIA pages (polite: 1.5 s delay, cache guard)
make segment     # raw_html → blocks.jsonl
make translate   # needs ANTHROPIC_API_KEY (or `ant auth login`); resumable
make qa          # deterministic checks; flags blocks
make site        # blocks.jsonl → site/<slug>/chapters/*.qmd
make render      # quarto render site/
```

All pipeline targets operate on one work, selected by `WORK` (default
`erfurter-programm`), e.g. `make segment WORK=another-work`.

Then iterate: review in browser → correct blocks.jsonl → `make site render`.

## Multi-work structure

The repo hosts several works of German Marxists; the site's root index groups them by
author. Work-specific facts live in a manifest, `works/<slug>/work.yaml` (author,
titles, year, MIA base URL, masthead headings to drop, translation-prompt text,
`legacy_url_prefix` for redirect aliases, and the chapter list). The pipeline code in
`pipeline/` is shared and work-parameterized: every script takes the work slug as its
first positional argument (`pipeline/common.py:parse_work_arg`), and `Work`/`Chapter`
dataclasses carry the manifest plus all derived paths.

```
pipeline/               shared, work-parameterized scripts
shared/glossary.yaml    common Marxist termbase
works/<slug>/           work.yaml + data/{raw_html/,blocks.jsonl} + book/ (EPUB project)
site/                   one combined Quarto website
  index.qmd             works index, grouped by author (hand-maintained)
  <slug>/               per-work pages: index/editorial/prologue + generated chapters/
```

The glossary is `shared/glossary.yaml` plus an optional per-work
`works/<slug>/data/glossary.yaml`; a per-work entry replaces any shared entry whose
German stem set overlaps its own, otherwise it is appended (`common.load_glossary`
prints a merge summary so overrides are visible).

`site/_quarto.yml` holds one *named* sidebar per work (`id: <slug>`), whose hrefs are
all prefixed with the work slug; Quarto shows each sidebar only on its own pages. The
root `index.qmd` sets `sidebar: false`.

### Adding a work (Milestone 2 recipe)

1. `mkdir works/<slug>` and write `work.yaml` (copy `works/erfurter-programm/work.yaml`
   as a template; chapter ids/titles from the MIA index page).
2. `make scrape segment WORK=<slug>`, sanity-check the block counts, then
   `make translate qa WORK=<slug>`.
3. Copy/adapt a `book/` Quarto book project (only `_quarto.yml` chapter list,
   `index.qmd`, cover) if an EPUB is wanted.
4. Hand-write `site/<slug>/index.qmd` (+ editorial notes as desired), append a
   `- id: <slug>` sidebar block to `site/_quarto.yml`, and add the work under its
   author on the root `site/index.qmd`.
5. `make site render` and review.

Nothing in `pipeline/` or the existing works should need to change.
