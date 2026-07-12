"""Shared constants and block I/O for the translation pipeline."""

import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_HTML = DATA / "raw_html"
BLOCKS_PATH = DATA / "blocks.jsonl"
GLOSSARY_PATH = DATA / "glossary.yaml"
SITE = ROOT / "site"
CHAPTERS_DIR = SITE / "chapters"

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
