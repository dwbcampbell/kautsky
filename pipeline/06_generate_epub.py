#!/usr/bin/env python3
"""Generate English-only Quarto book chapters from the work's blocks.jsonl.

Output: the work's book/chapters/*.qmd, rendered to EPUB by
`quarto render works/<slug>/book/` (book/_quarto.yml lists the chapters and
EPUB metadata; book/index.qmd is a static about-this-edition page).

Layout rules:
  - each chapter opens with `# {english title}` (the source h1 is skipped);
    the source pages use h4 for numbered sections, rendered as `##`
  - paragraphs / blockquotes / lists / tables: en_html passed through as a
    raw `{=html}` block (EPUB is XHTML, so inline HTML survives verbatim)
  - footnotes: English-only "Notes" section at the end of the chapter, with
    anchors remapped to chapter-unique IDs exactly as on the website
  - no status badges or German subtitles — this is a reading edition
  - Previous/Next navigation links added at bottom of each chapter
  - Return to TOC link added at bottom of each chapter
"""

from common import (flatten, heading_level, load_blocks, parse_work_arg,
                    remap_anchors, strip_tags)


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
    work = parse_work_arg()
    work.book_chapters_dir.mkdir(parents=True, exist_ok=True)
    blocks = load_blocks(work)
    by_chapter: dict[str, list[dict]] = {}
    for b in blocks:
        by_chapter.setdefault(b["chapter"], []).append(b)

    chapter_ids = [c.id for c in work.chapters]
    title_by_id = {c.id: c.title_en for c in work.chapters}

    for chapter in work.chapters:
        chapter_blocks = by_chapter.get(chapter.id, [])
        if not chapter_blocks:
            continue
        body = [b for b in chapter_blocks if b["type"] != "footnote"]
        notes = [b for b in chapter_blocks if b["type"] == "footnote"]

        out = [f"# {chapter.title_en}\n\n"]
        out += [render_block(b, chapter.id) for b in body]
        if notes:
            out.append("## Notes\n\n")
            out += [render_block(b, chapter.id) for b in notes]

        # Add navigation links
        idx = chapter_ids.index(chapter.id)
        prev_id = chapter_ids[idx - 1] if idx > 0 else None
        next_id = chapter_ids[idx + 1] if idx < len(chapter_ids) - 1 else None

        nav_links = []
        if prev_id:
            nav_links.append(f"[↑ Previous: {title_by_id[prev_id]}]({prev_id}.qmd)")
        nav_links.append("[↑ Return to Table of Contents](../index.qmd)")
        if next_id:
            nav_links.append(f"[Next: {title_by_id[next_id]} ↓]({next_id}.qmd)")

        out.append("\n---\n\n")
        out.append(" ".join(nav_links) + "\n")

        path = work.book_chapters_dir / f"{chapter.id}.qmd"
        path.write_text("".join(out), encoding="utf-8")
        print(f"wrote {path}  ({len(body)} blocks, {len(notes)} footnotes)")


if __name__ == "__main__":
    main()
