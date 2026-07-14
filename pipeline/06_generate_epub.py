#!/usr/bin/env python3
"""Generate English-only Quarto book chapters from data/blocks.jsonl.

Output: book/chapters/*.qmd, rendered to EPUB by `quarto render book/`
(book/_quarto.yml lists the chapters and EPUB metadata; book/index.qmd is a
static about-this-edition page).

Layout rules:
  - each chapter opens with `# {english title}` (the source h1 is skipped);
    the source pages use h4 for numbered sections, rendered as `##`
  - paragraphs / blockquotes / lists / tables: en_html passed through as a
    raw `{=html}` block (EPUB is XHTML, so inline HTML survives verbatim)
  - footnotes: English-only "Notes" section at the end of the chapter, with
    anchors remapped to chapter-unique IDs exactly as on the website
  - no status badges or German subtitles — this is a reading edition
"""

from common import (BOOK_CHAPTERS_DIR, CHAPTERS, flatten, heading_level,
                    load_blocks, remap_anchors, strip_tags)


def render_block(block: dict, chapter_id: str) -> str:
    en = block["en_html"]
    if not en:
        en = '<p class="todo">[not yet translated]</p>'
    en = flatten(remap_anchors(en, chapter_id))

    if block["type"] == "heading":
        if heading_level(block["de_html"]) == 1:
            return ""  # chapter title comes from the generated h1
        return f"## {strip_tags(en)}\n\n"

    return f"```{{=html}}\n{en}\n```\n\n"


def main() -> None:
    BOOK_CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    blocks = load_blocks()
    by_chapter: dict[str, list[dict]] = {}
    for b in blocks:
        by_chapter.setdefault(b["chapter"], []).append(b)

    for chapter_id, _, _, en_title in CHAPTERS:
        chapter_blocks = by_chapter.get(chapter_id, [])
        if not chapter_blocks:
            continue
        body = [b for b in chapter_blocks if b["type"] != "footnote"]
        notes = [b for b in chapter_blocks if b["type"] == "footnote"]

        out = [f"# {en_title}\n\n"]
        out += [render_block(b, chapter_id) for b in body]
        if notes:
            out.append("## Notes\n\n")
            out += [render_block(b, chapter_id) for b in notes]

        path = BOOK_CHAPTERS_DIR / f"{chapter_id}.qmd"
        path.write_text("".join(out), encoding="utf-8")
        print(f"wrote {path}  ({len(body)} blocks, {len(notes)} footnotes)")


if __name__ == "__main__":
    main()
