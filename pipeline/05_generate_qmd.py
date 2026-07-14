#!/usr/bin/env python3
"""Generate Quarto .qmd chapter pages from data/blocks.jsonl.

Layout rules:
  - headings: real Markdown headings (tags stripped, so the TOC stays clean),
    with the German original as a subtitle line
  - paragraphs / blockquotes / lists: parallel DE|EN columns (CSS grid)
  - tables: rendered full width, DE then EN, inside an overflow container
  - footnotes: bilingual section at the end of the page
  - footnote anchors are remapped to chapter-unique IDs (#n1 -> #ch2-n1)

Untranslated blocks render with a visible TODO marker in the English column,
so a draft site can be built at any stage of the translation.
"""

from common import (CHAPTERS, CHAPTERS_DIR, flatten, heading_level,
                    load_blocks, remap_anchors, strip_tags)

STATUS_BADGE = {"flagged": " ⚑", "untranslated": "", "translated": "", "verified": ""}


def render_block(block: dict, chapter_id: str) -> str:
    de = flatten(remap_anchors(block["de_html"], chapter_id))
    en = block["en_html"]
    en = flatten(remap_anchors(en, chapter_id)) if en else (
        '<p class="todo">[not yet translated]</p>'
    )
    badge = STATUS_BADGE.get(block["status"], "")

    if block["type"] == "heading":
        level = min(heading_level(block["de_html"]) + 1, 6)
        en_title = strip_tags(en) if block["en_html"] else strip_tags(de)
        de_title = strip_tags(de)
        out = "#" * level + f" {en_title}{badge}\n\n"
        if block["en_html"]:
            out += f'<p class="de-subtitle">{de_title}</p>\n\n'
        return out

    # `{=html}` raw blocks pass the HTML through verbatim. Without them,
    # pandoc parses text inside <p>...</p> as markdown — e.g. the numbered
    # demands of the Erfurt program ("1. Allgemeines ...") become ordered
    # lists that swallow the closing ::: fences.
    if block["type"] == "table":
        return (
            "::: {.table-block}\n\n"
            "```{=html}\n"
            f'<div class="table-scroll">\n{de}\n</div>\n'
            f'<div class="table-scroll">\n{en}\n</div>\n'
            "```\n\n"
            ":::\n\n"
        )

    return (
        "::: {.parallel-container}\n\n"
        f"::: {{.parallel-col-de}}\n\n```{{=html}}\n{de}\n```\n\n:::\n\n"
        f"::: {{.parallel-col-en}}\n\n```{{=html}}\n{en}\n```\n\n:::\n\n"
        ":::\n\n"
    )


def main() -> None:
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    blocks = load_blocks()
    by_chapter: dict[str, list[dict]] = {}
    for b in blocks:
        by_chapter.setdefault(b["chapter"], []).append(b)

    for chapter_id, _, de_title, en_title in CHAPTERS:
        chapter_blocks = by_chapter.get(chapter_id, [])
        if not chapter_blocks:
            continue
        body = [b for b in chapter_blocks if b["type"] != "footnote"]
        notes = [b for b in chapter_blocks if b["type"] == "footnote"]

        out = [f'---\ntitle: "{en_title}"\nsubtitle: "{de_title}"\n---\n\n']
        # The page h1 duplicates the front-matter title; skip it.
        out += [render_block(b, chapter_id) for b in body
                if not (b["type"] == "heading" and heading_level(b["de_html"]) == 1)]
        if notes:
            out.append("## Notes / Anmerkungen\n\n")
            out += [render_block(b, chapter_id) for b in notes]

        path = CHAPTERS_DIR / f"{chapter_id}.qmd"
        path.write_text("".join(out), encoding="utf-8")
        print(f"wrote {path}  ({len(body)} blocks, {len(notes)} footnotes)")


if __name__ == "__main__":
    main()
