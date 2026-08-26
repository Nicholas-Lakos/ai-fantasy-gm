# Automatically refreshes the full MLB The Show 26 Live Series OVR dataset.
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.theshowbase.com/players?series=Live&page={}"
OUT = Path("frontend/show_live_ratings.json")
MAX_PAGES = 200


def norm(name):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", name.lower())).strip()


def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.select("th,td")]
        # TheSHOWBASE currently exposes these columns in the overview table:
        # Card, Name, OVR, Meta Score, Position, Buy Now, Sell Now, Profit,
        # Profit %, Variations, Bats, Throws, Team, Rarity, Series, ...
        if len(cells) < 15:
            continue
        if cells[1].lower() in {"name", "player"}:
            continue
        if cells[14].strip().lower() != "live":
            continue
        name = cells[1].strip()
        try:
            ovr = int(cells[2].strip())
        except (TypeError, ValueError):
            continue
        if not name or not 40 <= ovr <= 99:
            continue
        rows.append({
            "name": name,
            "overall": ovr,
            "position": cells[4].strip(),
            "team": cells[12].strip(),
            "rarity": re.sub(r"^.*?\b(Red Diamond|Diamond|Gold|Silver|Bronze|Common)\b.*$", r"\1", cells[13].strip(), flags=re.I),
        })
    return rows


def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; AI-Fantasy-GM-Live-Ratings/2.0)",
        "Accept": "text/html,application/xhtml+xml",
    })

    by_name = {}
    empty_pages = 0

    # There are currently 136 pages (15 cards/page) for the 2,036 Live Series cards.
    # We intentionally allow more pages so the updater keeps working if the database grows.
    for page in range(1, MAX_PAGES + 1):
        r = session.get(BASE.format(page), timeout=30)
        r.raise_for_status()
        parsed = parse_page(r.text)
        if not parsed:
            empty_pages += 1
            if page > 136 and empty_pages >= 2:
                break
            continue
        empty_pages = 0
        for row in parsed:
            key = norm(row["name"])
            if key:
                by_name[key] = row

    players = sorted(by_name.values(), key=lambda x: x["name"].lower())
    if len(players) < 1900:
        raise RuntimeError(
            f"Only parsed {len(players)} Live Series players; refusing to publish incomplete data"
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "theSHOWBASE MLB The Show 26 Live Series",
        "source_url": "https://www.theshowbase.com/players?series=Live",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(players),
        "players": players,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Published {len(players)} Live Series ratings")


if __name__ == "__main__":
    main()
