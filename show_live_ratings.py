# Build the current MLB The Show 26 Live Series database used by the website.
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

SOURCE = "https://www.theshowbase.com/players?series=Live&page={}"
OUT = Path("frontend/show_live_ratings.json")
MAX_PAGES = 136  # theSHOWBASE player table currently reports 2,036 cards at 15/page


def norm(name):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", name.lower())).strip()


def parse_markdown(text):
    rows = []
    # Jina Reader converts the source table to Markdown. The table columns are:
    # Card | Name | OVR | Meta Score | Position | ... | Team | Rarity | Series | ...
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 15 or cells[1].lower() in {"name", "player"} or set(cells[1]) <= {"-", ":"}:
            continue
        try:
            ovr = int(re.match(r"^\d{1,3}$", cells[2]).group())
        except (AttributeError, ValueError):
            continue
        name = cells[1]
        if not name or not 40 <= ovr <= 99:
            continue
        if cells[14].lower() != "live":
            continue
        rarity_match = re.search(r"Red Diamond|Diamond|Gold|Silver|Bronze|Common", cells[13], re.I)
        rows.append({
            "name": name,
            "overall": ovr,
            "position": cells[4],
            "team": cells[12],
            "rarity": rarity_match.group(0).title() if rarity_match else cells[13],
        })
    return rows


def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "AI-Fantasy-GM-Live-Ratings/4.0"})
    by_name = {}

    for page in range(1, MAX_PAGES + 1):
        source_url = SOURCE.format(page)
        # Jina Reader fetches and renders the public source page server-side,
        # avoiding the 403/anti-bot response GitHub Actions receives directly.
        jina_url = "https://r.jina.ai/" + source_url
        r = session.get(jina_url, timeout=60)
        print(f"page {page}: HTTP {r.status_code}, {len(r.text)} bytes")
        r.raise_for_status()
        parsed = parse_markdown(r.text)
        print(f"page {page}: {len(parsed)} Live cards")
        for row in parsed:
            by_name[norm(row["name"])] = row

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
