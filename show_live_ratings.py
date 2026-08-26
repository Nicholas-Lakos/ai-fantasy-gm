# Build the current MLB The Show 26 Live Series database used by the website.
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import cloudscraper
from bs4 import BeautifulSoup

BASE = "https://www.theshowbase.com/players?series=Live&page={}"
OUT = Path("frontend/show_live_ratings.json")
MAX_PAGES = 41


def norm(name):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", name.lower())).strip()


def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.select("th,td")]
        if len(cells) < 15:
            continue
        if cells[1].lower() in {"name", "player"}:
            continue
        name = cells[1].strip()
        try:
            ovr = int(cells[2].strip())
        except (TypeError, ValueError):
            continue
        if not name or not 40 <= ovr <= 99:
            continue
        position = cells[4].strip()
        team = cells[12].strip()
        rarity_raw = cells[13].strip()
        m = re.search(r"Red Diamond|Diamond|Gold|Silver|Bronze|Common", rarity_raw, re.I)
        rarity = m.group(0).title() if m else rarity_raw
        rows.append({"name": name, "overall": ovr, "position": position, "team": team, "rarity": rarity})
    return rows


def main():
    # theSHOWBASE may challenge plain requests, so use a browser-like session.
    scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
    scraper.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.theshowbase.com/series/live",
    })

    by_name = {}
    for page in range(1, MAX_PAGES + 1):
        r = scraper.get(BASE.format(page), timeout=45)
        print(f"page {page}: HTTP {r.status_code}, {len(r.text)} bytes")
        r.raise_for_status()
        parsed = parse_page(r.text)
        print(f"page {page}: {len(parsed)} cards")
        for row in parsed:
            key = norm(row["name"])
            if key:
                by_name[key] = row

    players = sorted(by_name.values(), key=lambda x: x["name"].lower())
    if len(players) < 1900:
        raise RuntimeError(f"Only parsed {len(players)} unique Live Series players; refusing to publish incomplete data")

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
