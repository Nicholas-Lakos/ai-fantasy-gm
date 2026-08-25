# Automatically refreshes the full MLB The Show 26 Live Series OVR dataset.
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.theshowbase.com/players?series=Live&page={}"
OUT = Path("frontend/show_live_ratings.json")


def norm(name):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", name.lower())).strip()


def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.select("th,td")]
        if len(cells) < 2:
            continue
        lower = [x.lower() for x in cells]
        if "name" in lower and "ovr" in lower:
            continue
        if "live" not in " ".join(lower):
            continue
        ovr = None
        for i, cell in enumerate(cells):
            if re.fullmatch(r"\d{1,3}", cell) and 40 <= int(cell) <= 99:
                if i == 1 or (i > 0 and cells[0]):
                    ovr = int(cell)
                    break
        if ovr is None:
            m = re.search(r"\b([4-9]\d)\s+OVR\b", " ".join(cells), re.I)
            if m:
                ovr = int(m.group(1))
        if ovr is None:
            continue
        name = re.sub(r"\s+Live\b.*$", "", cells[0], flags=re.I).strip()
        if name and len(name) > 2:
            rows.append({"name": name, "overall": ovr})
    return rows


def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "AI-Fantasy-GM-Live-Ratings/1.0", "Accept": "text/html"})
    by_name = {}
    for page in range(1, 42):
        r = session.get(BASE.format(page), timeout=30)
        r.raise_for_status()
        for row in parse_page(r.text):
            key = norm(row["name"])
            if key:
                by_name[key] = row
    players = sorted(by_name.values(), key=lambda x: x["name"].lower())
    if len(players) < 1500:
        raise RuntimeError(f"Only parsed {len(players)} Live Series players; refusing to publish incomplete data")
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
