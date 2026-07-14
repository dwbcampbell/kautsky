"""Shared constants, block I/O, and HTML helpers for the translation pipeline."""

import json
import os
import re
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_HTML = DATA / "raw_html"
BLOCKS_PATH = DATA / "blocks.jsonl"
GLOSSARY_PATH = DATA / "glossary.yaml"
SITE = ROOT / "site"
CHAPTERS_DIR = SITE / "chapters"
BOOK = ROOT / "book"
BOOK_CHAPTERS_DIR = BOOK / "chapters"

BASE_URL = "https://www.marxists.org/deutsch/archiv/kautsky/1892/erfurter/"

# (chapter_id, source_file, german_title, english_title)
CHAPTERS = [
    ("vorwort-92", "vorwort-92.htm",
     "Vorwort zur ersten Auflage", "Preface to the First Edition"),
    ("vorwort-04", "vorwort-04.htm",
     "Vorrede zur fünften Auflage", "Preface to the Fifth Edition"),
    ("ch1", "1-untergang.htm",
     "I. Der Untergang des Kleinbetriebes", "I. The Decline of Small-Scale Enterprise"),
    ("ch2", "2-proletariat.htm",
     "II. Das Proletariat", "II. The Proletariat"),
    ("ch3", "3-kapitalisten.htm",
     "III. Die Kapitalistenklasse", "III. The Capitalist Class"),
    ("ch4", "4-zukunftsstaat.htm",
     "IV. Der Zukunftsstaat", "IV. The State of the Future"),
    ("ch5", "5-klassenkampf.htm",
     "V. Der Klassenkampf", "V. The Class Struggle"),
]


def load_blocks() -> list[dict]:
    blocks = []
    with open(BLOCKS_PATH, encoding="utf-8") as f:
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


def save_blocks(blocks: list[dict]) -> None:
    """Atomic write: never leave blocks.jsonl half-written on a crash."""
    fd, tmp = tempfile.mkstemp(dir=DATA, prefix=".blocks-", suffix=".jsonl")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for block in blocks:
                f.write(json.dumps(block, ensure_ascii=False) + "\n")
        os.replace(tmp, BLOCKS_PATH)
    except BaseException:
        os.unlink(tmp)
        raise
