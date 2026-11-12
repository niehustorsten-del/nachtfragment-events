#!/usr/bin/env python3
"""Build an artist-page keyed feed from published Nachtfragment concert data."""
from __future__ import annotations
import json, re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
ARTISTS_FILE = ROOT / "data" / "artists.json"
CONCERTS_FILE = ROOT / "concerts.json"
OUTPUT_FILE = ROOT / "data" / "artist-activity.json"
ALLOWED_STATUSES = {"confirmed", "date_confirmed", "lineup_announced", "date_confirmed_lineup_pending"}
SKIP_NAME = re.compile(r"newcomer|linkliste|weblinks|rezension|review|top\s*50|playlist|zwischen darkwave|bands|magazine|verzeichnis", re.I)

def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

def clean_name(value):
    name = re.sub(r"\s*[–-]\s*(Porträt|Portrait|Playlist|Linkliste).*$", "", value, flags=re.I).strip()
    words = name.split()
    if len(words) >= 4 and len(words) % 2 == 0:
        half = len(words) // 2
        if [w.casefold() for w in words[:half]] == [w.casefold() for w in words[half:]]:
            name = " ".join(words[:half])
    return name

def norm(value):
    return " ".join(re.findall(r"[^\W_]+", str(value or "").casefold(), flags=re.UNICODE))

def artist_slug(url):
    try:
        path = urlsplit(url).path.rstrip("/")
    except ValueError:
        return None
    match = re.fullmatch(r"/index\.php/artists/([a-z0-9-]+)", path, flags=re.I)
    return match.group(1).casefold() if match else None

def load_artists():
    result = {}
    for row in load_json(ARTISTS_FILE).get("artists", []):
        if not isinstance(row, dict):
            continue
        url = str(row.get("nachtfragment_url") or row.get("url") or "").strip()
        slug = artist_slug(url)
        name = clean_name(str(row.get("name") or row.get("artist") or "").strip())
        if slug and name and not SKIP_NAME.search(name):
            result.setdefault(slug, {"name": name, "url": url, "events": []})
    return result

def matches_artist(name, event):
    haystack = norm(" ".join(str(event.get(k) or "") for k in ("artist", "title")))
    needle = norm(name)
    return bool(needle and re.search(r"(?<![\w])" + re.escape(needle) + r"(?![\w])", haystack, flags=re.UNICODE))

def main():
    artists = load_artists()
    concert_data = load_json(CONCERTS_FILE)
    today = date.today().isoformat()
    seen = set()
    for event in concert_data.get("events", []):
        if not isinstance(event, dict):
            continue
        event_date = str(event.get("date") or "")[:10]
        status = str(event.get("status") or "").casefold()
        if status not in ALLOWED_STATUSES or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", event_date) or event_date < today:
            continue
        url = str(event.get("url") or "").strip()
        if not url.startswith(("https://", "http://")):
            continue
        for slug, artist in artists.items():
            if not matches_artist(artist["name"], event):
                continue
            event_id = str(event.get("id") or f'{slug}-{event_date}-{url}')
            if (slug, event_id) in seen:
                continue
            seen.add((slug, event_id))
            artist["events"].append({
                "id": event_id, "date": event_date,
                "title": str(event.get("title") or artist["name"]),
                "venue": str(event.get("venue") or ""), "city": str(event.get("city") or ""),
                "category": str(event.get("category") or "concert"), "status": status,
                "url": url, "source": str(event.get("source") or ""),
            })
    for artist in artists.values():
        artist["events"].sort(key=lambda item: (item["date"], item["city"], item["title"]))
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Nachtfragment published concerts.json",
        "artist_count": len(artists),
        "event_count": sum(len(a["events"]) for a in artists.values()),
        "artists": artists,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(OUTPUT_FILE)
    print(f"Artist Activity: {len(artists)} Künstlerseiten, {output['event_count']} bestätigte Termine.")

if __name__ == "__main__":
    main()
