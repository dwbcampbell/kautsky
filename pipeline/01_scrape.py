#!/usr/bin/env python3
"""Download and cache the German source pages from the Marxists Internet Archive.

Each page is fetched once (cache guard), decoded via the server's apparent
encoding, and re-written as normalized UTF-8. Polite: 1.5 s delay between
requests, identifying User-Agent.
"""

import time

import requests

from common import BASE_URL, CHAPTERS, RAW_HTML

HEADERS = {
    "User-Agent": "ErfurtTranslationProject/0.1 (dwbcampbell@gmail.com)"
}


def main() -> None:
    RAW_HTML.mkdir(parents=True, exist_ok=True)
    for _, filename, _, _ in CHAPTERS:
        dest = RAW_HTML / filename
        if dest.exists():
            print(f"cached   {filename}")
            continue

        r = requests.get(BASE_URL + filename, headers=HEADERS, timeout=30)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        dest.write_text(r.text, encoding="utf-8")
        print(f"fetched  {filename}  ({len(r.text)} chars)")
        time.sleep(1.5)


if __name__ == "__main__":
    main()
