#!/usr/bin/env python3
"""Build the public Nachtfragment Dark Music TV feed from existing editorial data."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ARTISTS_FILE = DATA / "artists.json"
NEWS_FILE = DATA / "artist-news.json"
CHARTS_FILE = DATA / "music-charts.json"
OUTPUT_FILE = DATA / "dmtv-feed.json"

SKIP_NAME_WORDS = ("newcomer", "linkliste", "weblinks", "rezension", "review",
                   "top 50", "zwischen darkwave", "magazine", "verzeichnis")


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def valid_url(value: object) -> str:
    value = str(value or "").strip()
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return value
    except ValueError:
        pass
    return ""


def clean_text(value: object, limit: int = 500) -> str:
    return " ".join(str(value or "").split())[:limit]


def artist_cards(artist_data: dict, week_key: str) -> list[dict]:
    rows = artist_data.get("artists", []) if isinstance(artist_data, dict) else []
    artists = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = clean_text(row.get("name") or row.get("artist"), 120)
        url = valid_url(row.get("nachtfragment_url") or row.get("url"))
        if not name or not url or name.casefold() in seen:
            continue
        if any(word in name.casefold() for word in SKIP_NAME_WORDS):
            continue
        seen.add(name.casefold())
        slug = urlsplit(url).path.rstrip("/").split("/")[-1]
        if not slug:
            continue
        # Rotate the visible sample weekly without changing or ranking the source directory.
        key = hashlib.sha256((week_key + "|" + slug).encode("utf-8")).hexdigest()
        artists.append((key, {"name": name, "url": url}))
    artists.sort(key=lambda item: item[0])
    return [item[1] for item in artists[:12]]


def approved_news(news_data: dict) -> list[dict]:
    rows = news_data.get("items", []) if isinstance(news_data, dict) else []
    items = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or str(row.get("status", "")).casefold() != "approved":
            continue
        url = valid_url(row.get("url"))
        title = clean_text(row.get("title"), 300)
        if not url or not title:
            continue
        key = str(row.get("id") or url).casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "id": key,
            "artist": clean_text(row.get("artist"), 120),
            "title": title,
            "summary": clean_text(row.get("summary"), 420),
            "date": clean_text(row.get("date"), 40),
            "category": clean_text(row.get("category") or "News", 60),
            "publisher": clean_text(row.get("publisher"), 100),
            "url": url,
        })
    items.sort(key=lambda item: item["date"], reverse=True)
    return items


def chart_highlights(chart_data: dict) -> list[dict]:
    rows = chart_data.get("tracks", []) if isinstance(chart_data, dict) else []
    result = []
    for index, row in enumerate(rows[:5], 1):
        if not isinstance(row, dict):
            continue
        artist = clean_text(row.get("artist"), 120)
        title = clean_text(row.get("title"), 180)
        if not artist or not title:
            continue
        link = valid_url(row.get("youtube") or row.get("bandcamp") or row.get("source") or row.get("spotify"))
        result.append({
            "position": int(row.get("position") or index),
            "artist": artist,
            "title": title,
            "genre": clean_text(row.get("genre"), 100),
            "release": clean_text(row.get("release"), 60),
            "url": link,
        })
    return result


def main():
    now = datetime.now(timezone.utc)
    week_key = now.strftime("%G-W%V")
    artist_data = load_json(ARTISTS_FILE, {})
    news_data = load_json(NEWS_FILE, {"items": []})
    chart_data = load_json(CHARTS_FILE, {"tracks": []})

    news = approved_news(news_data)
    videos = [
        item for item in news
        if "video" in item["category"].casefold()
        or "video" in item["title"].casefold()
        or "clip" in item["title"].casefold()
    ][:6]

    payload = {
        "title": "Nachtfragment Dark Music TV",
        "updated_at": now.isoformat(timespec="seconds"),
        "refresh": "Mittwoch und Sonntag; zusätzlich bei Änderungen an den Quelldaten",
        "sources": {
            "artists": "data/artists.json",
            "news": "data/artist-news.json (nur status=approved)",
            "charts": "data/music-charts.json",
        },
        "counts": {
            "artists_in_directory": len(artist_data.get("artists", [])) if isinstance(artist_data, dict) else 0,
            "approved_news": len(news),
            "video_news": len(videos),
            "chart_highlights": len(chart_highlights(chart_data)),
        },
        "underground_artists": artist_cards(artist_data, week_key),
        "videos": videos,
        "news": news[:8],
        "chart_highlights": chart_highlights(chart_data),
        "editorial_note": "Video-Einträge verlinken auf die jeweilige redaktionelle Meldung; sie sind keine eingebetteten YouTube-Player.",
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(OUTPUT_FILE)
    # Validate the exact output that will be published.
    check = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    assert isinstance(check.get("underground_artists"), list)
    assert isinstance(check.get("videos"), list)
    assert isinstance(check.get("news"), list)
    assert isinstance(check.get("chart_highlights"), list)
    print("DMTV_FEED_OK",
          "artists=", len(check["underground_artists"]),
          "videos=", len(check["videos"]),
          "news=", len(check["news"]),
          "charts=", len(check["chart_highlights"]))


if __name__ == "__main__":
    main()
