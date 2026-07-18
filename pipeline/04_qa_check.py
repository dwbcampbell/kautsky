#!/usr/bin/env python3
"""Deterministic QA over translated blocks.

Checks (cheap, mechanical — an LLM critique pass is only worth running on
whatever these flag):
  1. Length ratio: en/de character ratio outside [0.75, 1.60] suggests an
     omission or padding.
  2. Tag parity: the multiset of inline tags in en_html must match de_html
     (dropped <em>, lost footnote anchors, mangled tables).
  3. Glossary: if a German stem occurs in de_text, the required English term
     must appear in en_html and no 'avoid' term may appear.

Failures are recorded in each block's `qa` list and status is set to
'flagged'; clean translated blocks keep status 'translated'. Blocks already
marked 'verified' by human review are never touched.
"""

import re
from collections import Counter

from bs4 import BeautifulSoup

from common import load_blocks, load_glossary, parse_work_arg, save_blocks

RATIO_MIN, RATIO_MAX = 0.75, 1.60
TAG_RE = re.compile(r"<([a-zA-Z][a-zA-Z0-9]*)")
# Structural wrappers can legitimately differ in count (e.g. a long German
# paragraph split across <p>s is disallowed anyway, but list items are not).
IGNORED_TAGS = {"br"}


def tag_counts(html: str) -> Counter:
    return Counter(t.lower() for t in TAG_RE.findall(html)
                   if t.lower() not in IGNORED_TAGS)


def snippet(text: str, term: str, width: int = 30) -> str:
    """Short excerpt of `text` around the first occurrence of `term`."""
    i = text.lower().find(term.lower())
    if i < 0:
        return ""
    start, end = max(i - width, 0), i + len(term) + width
    return (("…" if start > 0 else "") + text[start:end].strip()
            + ("…" if end < len(text) else ""))


def check_block(block: dict, glossary: list[dict]) -> list[str]:
    problems = []
    de_text = block["de_text"]
    en_html = block["en_html"]
    en_text = BeautifulSoup(en_html, "lxml").get_text(" ", strip=True)

    if block["type"] != "table":  # numeric tables have wild char ratios
        ratio = len(en_text) / max(len(de_text), 1)
        if not RATIO_MIN <= ratio <= RATIO_MAX:
            problems.append(f"length ratio {ratio:.2f} outside "
                            f"[{RATIO_MIN}, {RATIO_MAX}] "
                            f"(en {len(en_text)} / de {len(de_text)} chars)")

    de_tags, en_tags = tag_counts(block["de_html"]), tag_counts(en_html)
    if de_tags != en_tags:
        diff = {t: (de_tags[t], en_tags[t])
                for t in de_tags.keys() | en_tags.keys()
                if de_tags[t] != en_tags[t]}
        problems.append(f"tag mismatch (de, en): {diff}")

    de_lower, en_lower = de_text.lower(), en_text.lower()
    for entry in glossary:
        matched = [stem for stem in entry["de"] if stem in de_lower]
        if matched:
            if entry["en"].lower() not in en_lower:
                problems.append(
                    f"glossary: expected '{entry['en']}' for de stem "
                    f"'{matched[0]}' (de: \"{snippet(de_text, matched[0])}\")")
            for avoid in entry.get("avoid", []):
                if avoid.lower() in en_lower:
                    problems.append(
                        f"glossary: found avoided term '{avoid}' "
                        f"(en: \"{snippet(en_text, avoid)}\"; "
                        f"use '{entry['en']}')")
    return problems


def main() -> None:
    work = parse_work_arg()
    glossary = load_glossary(work)
    blocks = load_blocks(work)

    checked = flagged = 0
    for block in blocks:
        if not block.get("en_html") or block["status"] == "verified":
            continue
        problems = check_block(block, glossary)
        block["qa"] = problems
        block["status"] = "flagged" if problems else "translated"
        checked += 1
        if problems:
            flagged += 1
            print(f"{block['id']} [{block['type']}]")
            for p in problems:
                print(f"    {p}")

    save_blocks(work, blocks)
    print(f"\nchecked {checked} blocks, flagged {flagged}")


if __name__ == "__main__":
    main()
