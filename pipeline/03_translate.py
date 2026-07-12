#!/usr/bin/env python3
"""Translate German blocks to English with the Anthropic API.

Design (see Plan.md):
- Blocks are grouped into heading-bounded, size-capped sections so the model
  sees real discourse context and returns one entry per block ID.
- The full German chapter rides along as a cached system block: every request
  after the first per chapter reads it at ~0.1x price, and pronoun reference
  never drifts for lack of antecedent context.
- Structured outputs guarantee a parseable {id -> en_html} array.
- Progress is written back to data/blocks.jsonl after every section, so the
  script can be interrupted and re-run at any time.

Auth: ANTHROPIC_API_KEY env var, or an `ant auth login` profile.
"""

import json
import sys

import anthropic
import yaml

from common import GLOSSARY_PATH, load_blocks, save_blocks

MODEL = "claude-opus-4-8"
MAX_TOKENS = 16000
MAX_BLOCKS_PER_SECTION = 15
MAX_CHARS_PER_SECTION = 8000

SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "en_html": {"type": "string"},
                },
                "required": ["id", "en_html"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["translations"],
    "additionalProperties": False,
}

SYSTEM_TEMPLATE = """\
You are a scholarly translator of historical socialist theory, translating Karl \
Kautsky's 'Das Erfurter Programm' (1892) from German into precise, complete, \
unabridged English.

RULES:
1. Completeness is the highest priority. Never merge, split, summarize, or omit \
a single clause. (The 1910 Bohn edition was abridged; this edition must be \
strictly complete.)
2. Apply this glossary strictly:
{glossary}
3. Render Kautsky's formal analytical German in clear, readable academic \
English. Use British spelling conventions ('labour', 'socialisation'). Long \
German periodic sentences may be divided into several English sentences where \
clarity requires it, but nothing may be dropped.
4. Each input block is an HTML fragment. Return the translated fragment with \
the SAME outer tag and ALL inline HTML (<em>, <strong>, <a> anchors and hrefs, \
<sub>, <sup>) preserved exactly in place around the corresponding translated text.
5. Tables: translate only header and word cells; never alter numeric data, \
column structure, or attributes.
6. Headings: translate the text; keep the tag.
7. Return exactly one translation entry per input block id, in the same order.
"""


def build_system(glossary_text: str, chapter_de_text: str) -> list[dict]:
    return [
        {"type": "text", "text": SYSTEM_TEMPLATE.format(glossary=glossary_text)},
        {
            "type": "text",
            "text": (
                "Full German text of the current chapter, for context. Use it to "
                "resolve pronoun references and terminology consistently; translate "
                "only the blocks given in the user message.\n\n" + chapter_de_text
            ),
            "cache_control": {"type": "ephemeral"},
        },
    ]


def sections(blocks: list[dict]):
    """Yield heading-bounded, size-capped batches of untranslated blocks."""
    batch: list[dict] = []
    chars = 0
    for b in blocks:
        starts_new = (
            (b["type"] == "heading" and batch)
            or len(batch) >= MAX_BLOCKS_PER_SECTION
            or chars + len(b["de_html"]) > MAX_CHARS_PER_SECTION
        )
        if starts_new and batch:
            yield batch
            batch, chars = [], 0
        batch.append(b)
        chars += len(b["de_html"])
    if batch:
        yield batch


def translate_section(client: anthropic.Anthropic, system: list[dict],
                      section: list[dict]) -> dict[str, str]:
    payload = [{"id": b["id"], "type": b["type"], "de_html": b["de_html"]}
               for b in section]
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{
            "role": "user",
            "content": (
                "Translate each of the following blocks. Return one entry per id.\n\n"
                + json.dumps(payload, ensure_ascii=False)
            ),
        }],
    )
    if response.stop_reason == "max_tokens":
        raise RuntimeError("response truncated (max_tokens) — reduce section size")
    if response.stop_reason == "refusal":
        raise RuntimeError("request refused")
    text = next(b.text for b in response.content if b.type == "text")
    result = {t["id"]: t["en_html"] for t in json.loads(text)["translations"]}
    missing = [b["id"] for b in section if b["id"] not in result]
    if missing:
        raise RuntimeError(f"missing translations for {missing}")
    return result


def main() -> None:
    # Optional args restrict the run to specific chapters, e.g.:
    #   python pipeline/03_translate.py vorwort-92 ch1
    only = set(sys.argv[1:])
    client = anthropic.Anthropic()
    glossary_text = yaml.dump(
        yaml.safe_load(GLOSSARY_PATH.read_text(encoding="utf-8")),
        allow_unicode=True, sort_keys=False,
    )
    blocks = load_blocks()
    by_id = {b["id"]: b for b in blocks}

    chapters: dict[str, list[dict]] = {}
    for b in blocks:
        chapters.setdefault(b["chapter"], []).append(b)

    done = failed = 0
    for chapter_id, chapter_blocks in chapters.items():
        if only and chapter_id not in only:
            continue
        todo = [b for b in chapter_blocks if not b.get("en_html")]
        if not todo:
            continue
        chapter_de_text = "\n\n".join(b["de_text"] for b in chapter_blocks)
        system = build_system(glossary_text, chapter_de_text)
        print(f"\n=== {chapter_id}: {len(todo)} blocks to translate ===")

        for section in sections(todo):
            ids = f"{section[0]['id']} .. {section[-1]['id']}"
            try:
                result = translate_section(client, system, section)
            except (anthropic.APIError, RuntimeError, json.JSONDecodeError) as e:
                failed += len(section)
                print(f"  FAILED  {ids}: {e}", file=sys.stderr)
                continue
            for block_id, en_html in result.items():
                by_id[block_id]["en_html"] = en_html
                by_id[block_id]["status"] = "translated"
            done += len(section)
            save_blocks(blocks)
            print(f"  ok      {ids}  ({len(section)} blocks)")

    print(f"\ntranslated {done} blocks"
          + (f", {failed} failed (re-run to retry)" if failed else ""))


if __name__ == "__main__":
    main()
