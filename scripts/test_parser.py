#!/usr/bin/env python3
"""Local parser change-detection test.

Fetches the live Granicus page, then:
  1. Confirms parser correctly identifies the 5/16 row as UNLINKED today.
  2. Injects a fake <a href> into that row, parses again, and confirms the
     parser would FIRE — returning a properly-normalized https:// URL.

This is the test that proves the alert pipeline will trigger when the agenda
actually gets published. Run anytime:

    .venv/bin/python scripts/test_parser.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import requests
from bs4 import BeautifulSoup

from poll import (
    GRANICUS_URL,
    TARGET_DATE,
    TARGET_LABEL_HINT,
    find_target_row,
)

FAKE_HREF = "//alexandria.granicus.com/AgendaViewer.php?view_id=57&event_id=99999"
EXPECTED_NORMALIZED = "https://alexandria.granicus.com/AgendaViewer.php?view_id=57&event_id=99999"


def inject_link_into_target_row(html: str) -> str:
    """Return a copy of html where the 5/16 row's title cell is wrapped in an <a>."""
    soup = BeautifulSoup(html, "html.parser")
    for row in soup.find_all("tr"):
        row_text = row.get_text(" | ", strip=True)
        if TARGET_DATE not in row_text or TARGET_LABEL_HINT not in row_text:
            continue
        title_cell = None
        for cell in row.find_all("td"):
            if TARGET_LABEL_HINT in cell.get_text():
                title_cell = cell
                break
        if title_cell is None:
            raise RuntimeError("Title cell not found inside target row")
        original_title = title_cell.get_text(strip=True)
        title_cell.clear()
        anchor = soup.new_tag("a", href=FAKE_HREF)
        anchor.string = original_title
        title_cell.append(anchor)
        return str(soup)
    raise RuntimeError(f"Target row not found (date={TARGET_DATE} hint={TARGET_LABEL_HINT})")


def main() -> int:
    print(f"Fetching {GRANICUS_URL} ...")
    resp = requests.get(
        GRANICUS_URL,
        timeout=30,
        headers={"User-Agent": "safer-braddock-watch/test"},
    )
    resp.raise_for_status()
    html = resp.text

    # ---- Test 1: live page should currently show 5/16 as UNLINKED ----
    row_text, url, valid = find_target_row(html)
    assert valid, "FAIL: page validity check failed on live page"
    assert row_text is not None, f"FAIL: target row not found on live page (target={TARGET_DATE})"
    assert url is None, f"FAIL: expected no link on live page, got {url!r} (did agenda just publish?!)"
    print(f"  PASS  live page: row='{row_text}' link=None")

    # ---- Test 2: doctored page with injected link should fire ----
    doctored = inject_link_into_target_row(html)
    row_text2, url2, valid2 = find_target_row(doctored)
    assert valid2, "FAIL: page validity check failed on doctored page"
    assert row_text2 is not None, "FAIL: target row not found on doctored page"
    assert url2 == EXPECTED_NORMALIZED, (
        f"FAIL: expected {EXPECTED_NORMALIZED!r}, got {url2!r}"
    )
    print(f"  PASS  doctored page: row='{row_text2}' link='{url2}'")

    print("\nAll parser change-detection tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
