# Kautsky *Erfurter Programm* — Parallel Translation Project

Produce a complete, unabridged, terminologically consistent English translation of Karl
Kautsky's *Das Erfurter Programm in seinem grundsätzlichen Theil erläutert* (1892), and
publish it as a bilingual parallel-column website built with Quarto.

**Why:** the standard English translation (William E. Bohn, *The Class Struggle*, 1910)
compresses the German text to roughly two-thirds of its length — omitting illustrative
passages, statistical tables, and nuance — and renders core terminology inconsistently.

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
copyright; state a license (e.g. CC BY-SA) in `site/editorial.qmd`.

## Pipeline

```
[ MIA German HTML ] ─► 01_scrape ──► data/raw_html/            (cached, one-time)
                       02_segment ─► data/blocks.jsonl         (one block per line — SOURCE OF TRUTH)
                       03_translate ► en_html filled in-place  (Anthropic API, resumable)
                       04_qa_check ─► blocks flagged in-place  (deterministic checks first)
                       05_generate ─► site/chapters/*.qmd
                       quarto render site/ ─► parallel bilingual website
```

A single file, `data/blocks.jsonl`, is the source of truth. Each line is one block:

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

`data/glossary.yaml` — the contract that fixes Bohn's inconsistencies. Each entry:
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
make scrape      # cache the 7 MIA pages (polite: 1.5 s delay, cache guard)
make segment     # raw_html → data/blocks.jsonl
make translate   # needs ANTHROPIC_API_KEY (or `ant auth login`); resumable
make qa          # deterministic checks; flags blocks
make site        # blocks.jsonl → site/chapters/*.qmd
make render      # quarto render site/
```

Then iterate: review in browser → correct blocks.jsonl → `make site render`.
