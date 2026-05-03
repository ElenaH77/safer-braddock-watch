#!/usr/bin/env python3
"""Poll Alexandria's Granicus calendar for the May 16, 2026 City Council Public
Hearing. Fire Pushover emergency alert the moment that row gains an agenda link.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

GRANICUS_URL = "https://alexandria.granicus.com/ViewPublisher.php?view_id=57"
TARGET_DATE = "05/16/26"
TARGET_LABEL_HINT = "City Council"
STATE_PATH = Path("state/last_seen.json")

PUSHOVER_USER = os.environ.get("PUSHOVER_USER", "")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN", "")
TEST_ALERT = os.environ.get("TEST_ALERT", "").lower() in ("true", "1", "yes")


def fetch_granicus() -> str:
    resp = requests.get(
        GRANICUS_URL,
        timeout=30,
        headers={"User-Agent": "safer-braddock-watch/1.0 (advocacy monitor)"},
    )
    resp.raise_for_status()
    return resp.text


def find_target_row(html: str):
    """Return (row_text, agenda_url_or_None, page_looks_valid)."""
    page_valid = "Upcoming Meetings" in html and "ViewPublisher" in html
    soup = BeautifulSoup(html, "html.parser")

    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        row_text = row.get_text(" | ", strip=True)
        if TARGET_DATE not in row_text:
            continue
        if TARGET_LABEL_HINT not in row_text:
            continue
        link = row.find("a", href=True)
        href = None
        if link:
            href = link["href"]
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = "https://alexandria.granicus.com" + href
        return row_text, href, page_valid

    return None, None, page_valid


def fire_pushover(title: str, message: str, priority: int = 2, url: str | None = None):
    if not PUSHOVER_USER or not PUSHOVER_TOKEN:
        print(f"[would-alert priority={priority}] {title}: {message}", file=sys.stderr)
        return
    data = {
        "user": PUSHOVER_USER,
        "token": PUSHOVER_TOKEN,
        "title": title,
        "message": message,
        "priority": priority,
    }
    if priority == 2:
        data["retry"] = 30
        data["expire"] = 3600
    if url:
        data["url"] = url
        data["url_title"] = "Open agenda"
    resp = requests.post(
        "https://api.pushover.net/1/messages.json", data=data, timeout=20
    )
    resp.raise_for_status()


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}


def save_state(state: dict):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def main():
    now = datetime.now(timezone.utc).isoformat()

    if TEST_ALERT:
        fire_pushover(
            "Safer Braddock test",
            "End-to-end test from GitHub Actions. If you got this, the watcher is wired up correctly.",
            priority=1,
        )
        print(f"[{now}] Test alert fired.")
        return

    html = fetch_granicus()
    row_text, agenda_url, page_valid = find_target_row(html)
    state = load_state()

    if not page_valid:
        today = now[:10]
        if state.get("last_page_invalid_alert") != today:
            fire_pushover(
                "Safer Braddock watcher: page structure changed",
                f"Granicus page no longer matches expected structure. Manual check needed:\n{GRANICUS_URL}",
                priority=0,
            )
            state["last_page_invalid_alert"] = today
        state["last_check"] = now
        save_state(state)
        sys.exit("Page validity check failed — site may be down or restructured.")

    if row_text is None:
        if state.get("target_seen") and not state.get("target_url"):
            fire_pushover(
                "5/16 row missing from Granicus",
                f"The 05/16/26 City Council Public Hearing row is gone. Meeting cancelled or rescheduled?\n\n{GRANICUS_URL}",
                priority=0,
            )
        state["target_seen"] = False
        state["target_url"] = None
        state["last_check"] = now
        save_state(state)
        print(f"[{now}] Target row not found.")
        return

    previously_url = state.get("target_url")

    if agenda_url and not previously_url:
        fire_pushover(
            "5/16 AGENDA PUBLISHED — sign up NOW",
            f"{row_text}\n\nAgenda link is live on Granicus. Speaker signup form should accept this date now.\n\nSend the newsletter and email blast.",
            priority=2,
            url=agenda_url,
        )
        print(f"[{now}] EMERGENCY ALERT FIRED — agenda live: {agenda_url}")
    elif agenda_url and previously_url != agenda_url:
        fire_pushover(
            "5/16 agenda URL changed",
            f"{row_text}\n\nNew URL: {agenda_url}\nOld URL: {previously_url}",
            priority=0,
            url=agenda_url,
        )
        print(f"[{now}] Agenda URL changed: {previously_url} -> {agenda_url}")
    else:
        print(f"[{now}] OK — row='{row_text}' linked={'yes' if agenda_url else 'no'}")

    state["target_seen"] = True
    state["target_url"] = agenda_url
    state["target_row"] = row_text
    state["last_check"] = now
    save_state(state)


if __name__ == "__main__":
    main()
