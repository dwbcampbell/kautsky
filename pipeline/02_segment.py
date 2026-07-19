#!/usr/bin/env python3
"""Segment the cached MIA HTML into aligned translation blocks.

Output: the work's data/blocks.jsonl — one JSON object per line, the
pipeline's source of truth. Existing translations are preserved on re-runs:
blocks are keyed by a content hash of the German text, so a segmenter fix
never orphans work already done.

MIA markup conventions (verified against the cached pages):
  - masthead:   author/title headings (work.yaml masthead_texts)  -> drop
  - navigation: p.link / p.toplink / p.updat                      -> drop
  - quotations: p.quote / p.quoteb (program text etc.)            -> blockquote
  - footnotes:  h3 "Anmerkungen …"/"Fußnote(n)" then p.note       -> footnote
  - content tables (statistics, equations): no hyperlinks         -> table
"""

import hashlib
import re
import sys

from bs4 import BeautifulSoup, Tag

from common import load_blocks, parse_work_arg, save_blocks

BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "p", "blockquote", "table", "ol", "ul"]
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5"}

DROP_P_CLASSES = {"link", "toplink", "linkback", "updat", "information", "footer", "toc"}
QUOTE_P_CLASSES = {"quote", "quoteb", "quotec"}
NOTES_HEADING = re.compile(r"^(anmerkung|fußnote|fussnote)", re.I)

# Fallback footnote signal: definition anchors like <a name="n2">.
FOOTNOTE_ANCHOR = re.compile(r"^(n|fn|note)\d+$", re.I)


def looks_like_data_table(table: Tag) -> bool:
    """Content tables (statistics, display equations, datelines) carry no
    hyperlinks; MIA navigation tables always do. Empty-text tables (e.g.
    image-only) are already skipped by the caller."""
    return table.find("a", href=True) is None


def classify(el: Tag, text: str, in_notes: bool, masthead_texts: frozenset[str]) -> str | None:
    """Return block type, 'NOTES_START' for the notes heading, or None to drop."""
    classes = set(el.get("class") or [])

    if el.name in HEADING_TAGS:
        if text.lower() in masthead_texts:
            return None
        if NOTES_HEADING.match(text):
            return "NOTES_START"
        return "heading"

    if el.name == "table":
        return "table" if looks_like_data_table(el) else None

    if el.name in ("ol", "ul"):
        links = el.find_all("a", href=True)
        items = el.find_all("li")
        if items and links and len(links) >= len(items):
            return None  # navigation list
        return "list"

    # p / blockquote
    if classes & DROP_P_CLASSES:
        return None
    if in_notes or "note" in classes or el.find("a", attrs={"name": FOOTNOTE_ANCHOR}):
        return "footnote"
    if el.name == "blockquote" or classes & QUOTE_P_CLASSES:
        return "blockquote"
    return "paragraph"


def top_level_blocks(soup: BeautifulSoup) -> list[Tag]:
    """All block elements, minus any nested inside another selected element."""
    root = soup.body or soup
    selected = root.find_all(BLOCK_TAGS)
    ids = {id(el) for el in selected}
    return [el for el in selected if not any(id(p) in ids for p in el.parents)]


def segment_chapter(chapter_id: str, html: str,
                    masthead_texts: frozenset[str]) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    blocks: list[dict] = []
    seen_hashes: dict[str, int] = {}
    in_notes = False

    for el in top_level_blocks(soup):
        text = el.get_text(" ", strip=True)
        if not text:
            continue

        btype = classify(el, text, in_notes, masthead_texts)
        if btype == "NOTES_START":
            # We render our own bilingual notes heading; everything from here
            # to the end of the page is footnote material.
            in_notes = True
            continue
        if btype is None:
            continue

        h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
        n = seen_hashes.get(h, 0)
        seen_hashes[h] = n + 1
        block_id = f"{chapter_id}-{h}" if n == 0 else f"{chapter_id}-{h}-{n + 1}"

        blocks.append(
            {
                "id": block_id,
                "chapter": chapter_id,
                "type": btype,
                "de_html": str(el),
                "de_text": text,
                "en_html": None,
                "status": "untranslated",
                "qa": [],
            }
        )
    return blocks


def main() -> None:
    work = parse_work_arg()

    # Preserve existing translations across re-segmentation.
    existing: dict[str, dict] = {}
    if work.blocks_path.exists():
        existing = {b["id"]: b for b in load_blocks(work)}

    all_blocks: list[dict] = []
    for chapter in work.chapters:
        path = work.raw_html / chapter.source
        if not path.exists():
            sys.exit(f"missing {path} — run pipeline/01_scrape.py first")
        chapter_blocks = segment_chapter(chapter.id, path.read_text(encoding="utf-8"),
                                         work.masthead_texts)
        carried = 0
        for b in chapter_blocks:
            old = existing.get(b["id"])
            if old and old.get("en_html"):
                b.update(en_html=old["en_html"], status=old["status"], qa=old.get("qa", []))
                carried += 1
        counts: dict[str, int] = {}
        for b in chapter_blocks:
            counts[b["type"]] = counts.get(b["type"], 0) + 1
        print(f"{chapter.id:12s} {len(chapter_blocks):4d} blocks  {counts}"
              + (f"  ({carried} translations carried over)" if carried else ""))
        all_blocks.extend(chapter_blocks)

    save_blocks(work, all_blocks)
    print(f"\nwrote {len(all_blocks)} blocks to {work.blocks_path}")


if __name__ == "__main__":
    main()
