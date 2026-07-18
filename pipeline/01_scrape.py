#!/usr/bin/env python3
"""Download and cache the German source pages from the Marxists Internet Archive.

Each page is fetched once (cache guard), decoded via the server's apparent
encoding, and re-written as normalized UTF-8. Polite: 1.5 s delay between
requests, identifying User-Agent.
"""

import time

import requests

from common import parse_work_arg

HEADERS = {
    "User-Agent": "MarxistsTranslationProject/0.1 (dwbcampbell@gmail.com)"
}


def main() -> None:
    work = parse_work_arg()
    work.raw_html.mkdir(parents=True, exist_ok=True)
    for chapter in work.chapters:
        dest = work.raw_html / chapter.source
        if dest.exists():
            print(f"cached   {chapter.source}")
            continue

        r = requests.get(work.base_url + chapter.source, headers=HEADERS, timeout=30)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        dest.write_text(r.text, encoding="utf-8")
        print(f"fetched  {chapter.source}  ({len(r.text)} chars)")
        time.sleep(1.5)


if __name__ == "__main__":
    main()
