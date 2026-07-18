"""Shared work loading, block I/O, and HTML helpers for the translation pipeline.

Work-specific facts (source URLs, chapter lists, prompt text) live in
works/<slug>/work.yaml; every pipeline script takes the work slug as its
first positional argument and gets a `Work` back from `parse_work_arg()`.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
WORKS = ROOT / "works"
SHARED_GLOSSARY_PATH = ROOT / "shared" / "glossary.yaml"
SITE = ROOT / "site"


@dataclass(frozen=True)
class Chapter:
    id: str
    source: str          # filename on the MIA site and in data/raw_html/
    title_de: str
    title_en: str


@dataclass(frozen=True)
class Work:
    slug: str
    author: str
    title_de: str
    title_full_de: str
    title_en: str
    year: int
    base_url: str
    masthead_texts: frozenset[str]      # lowercased headings to drop
    translation_description: str        # opening sentence of the system prompt
    completeness_note: str              # appended to the completeness rule
    legacy_url_prefix: str | None       # old URL prefix to emit aliases for
    chapters: tuple[Chapter, ...] = field(default=())

    @property
    def root(self) -> Path:
        return WORKS / self.slug

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def raw_html(self) -> Path:
        return self.data / "raw_html"

    @property
    def blocks_path(self) -> Path:
        return self.data / "blocks.jsonl"

    @property
    def glossary_path(self) -> Path:
        """Optional per-work glossary extension."""
        return self.data / "glossary.yaml"

    @property
    def book_dir(self) -> Path:
        return self.root / "book"

    @property
    def book_chapters_dir(self) -> Path:
        return self.book_dir / "chapters"

    @property
    def site_dir(self) -> Path:
        return SITE / self.slug

    @property
    def site_chapters_dir(self) -> Path:
        return self.site_dir / "chapters"


def available_slugs() -> list[str]:
    return sorted(p.parent.name for p in WORKS.glob("*/work.yaml"))


def load_work(slug: str) -> Work:
    manifest_path = WORKS / slug / "work.yaml"
    if not manifest_path.exists():
        sys.exit(f"unknown work '{slug}' — available: {', '.join(available_slugs())}")
    m = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    translation = m.get("translation") or {}
    return Work(
        slug=m["slug"],
        author=m["author"],
        title_de=m["title_de"],
        title_full_de=m.get("title_full_de", m["title_de"]),
        title_en=m["title_en"],
        year=m["year"],
        base_url=m["base_url"],
        masthead_texts=frozenset(t.lower() for t in m.get("masthead_texts", [])),
        translation_description=translation.get("description", "").strip(),
        completeness_note=translation.get("completeness_note", "").strip(),
        legacy_url_prefix=m.get("legacy_url_prefix"),
        chapters=tuple(Chapter(**c) for c in m["chapters"]),
    )


def parse_work_arg(extra_args: bool = False, description: str | None = None):
    """Parse the work slug (first positional arg) common to all pipeline scripts.

    Returns the Work, or (Work, remaining_args) when `extra_args` is true.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("work", help="work slug, e.g. " + ", ".join(available_slugs()))
    if extra_args:
        parser.add_argument("extra", nargs="*",
                            help="optional chapter ids to restrict the run")
    args = parser.parse_args()
    work = load_work(args.work)
    return (work, args.extra) if extra_args else work


def load_glossary(work: Work) -> list[dict]:
    """Shared glossary plus the work's optional extension.

    A per-work entry replaces any shared entry whose `de` stem set intersects
    its own (case-insensitive); otherwise it is appended.
    """
    shared = yaml.safe_load(SHARED_GLOSSARY_PATH.read_text(encoding="utf-8")) or []
    if not work.glossary_path.exists():
        return shared
    local = yaml.safe_load(work.glossary_path.read_text(encoding="utf-8")) or []

    merged = list(shared)
    overridden = 0
    for entry in local:
        stems = {s.lower() for s in entry["de"]}
        overlapping = [i for i, e in enumerate(merged)
                       if stems & {s.lower() for s in e["de"]}]
        for i in overlapping:
            merged[i] = None
            overridden += 1
        merged = [e for e in merged if e is not None]
        merged.append(entry)
    print(f"merged glossary: {len(shared)} shared + {len(local)} work "
          f"({overridden} overridden)")
    return merged


def load_blocks(work: Work) -> list[dict]:
    blocks = []
    with open(work.blocks_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                blocks.append(json.loads(line))
    return blocks


def strip_tags(html: str) -> str:
    return BeautifulSoup(html, "lxml").get_text(" ", strip=True)


def remap_anchors(html: str, chapter_id: str) -> str:
    """Make footnote anchor names/hrefs unique per chapter."""
    html = re.sub(r'href="#([^"]+)"', rf'href="#{chapter_id}-\1"', html)
    html = re.sub(r'(name|id)="([^"]+)"', rf'\1="{chapter_id}-\2"', html)
    return html


def heading_level(de_html: str) -> int:
    m = re.match(r"<h(\d)", de_html)
    return int(m.group(1)) if m else 3


def flatten(html: str) -> str:
    """Single-line HTML: newlines/indentation inside a block would otherwise
    be re-parsed by pandoc as blank lines or indented code."""
    return re.sub(r"\s*\n\s*", " ", html).strip()


def save_blocks(work: Work, blocks: list[dict]) -> None:
    """Atomic write: never leave blocks.jsonl half-written on a crash."""
    fd, tmp = tempfile.mkstemp(dir=work.data, prefix=".blocks-", suffix=".jsonl")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for block in blocks:
                f.write(json.dumps(block, ensure_ascii=False) + "\n")
        os.replace(tmp, work.blocks_path)
    except BaseException:
        os.unlink(tmp)
        raise
