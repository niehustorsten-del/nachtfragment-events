#!/usr/bin/env python3
"""
Nachtfragment Concert Discovery — additive module.
Does not modify updater.py or data/nachtfragment.json.
Requires SERPAPI_KEY in GitHub Actions secrets.
"""
from __future__ import annotations
import json, os, re, time
from datetime import datetime, date, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from html.parser import HTMLParser

SITE = os.getenv("NACHTFRAGMENT_SITE", "https://nachtfragment.de")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()
ARTISTS_PATH = "data/artists.json"
CONCERTS_PATH = "data/concerts.json"
CANDIDATES_PATH = "data/concert_candidates.json"
USER_AGENT = "Nachtfragment-Concert-Discovery/1.0 (+https://nachtfragment.de)"

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = False
        self.h1 = False
        self.in_title = False
        self.in_h1 = False
        self.title_text = []
        self.h1_text = []
        self.meta = {}
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.in_h1 = True
        elif tag == "meta":
            key = attrs.get("property") or attrs.get("name")
            if key and attrs.get("content"):
                self.meta[key.lower()] = attrs["content"]
    def handle_endtag(self, tag):
        if tag == "title": self.in_title = False
        if tag == "h1": self.in_h1 = False
    def handle_data(self, data):
        if self.in_title: self.title_text.append(data.strip())
        if self.in_h1: self.h1_text.append(data.strip())

def fetch(url, timeout=20):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as r:
        return r.read()

def load_json(path, fallback):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except (OSError, json.JSONDecodeError): return fallback

def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

def site_urls():
    urls = set()
    for sitemap in (SITE.rstrip("/") + "/sitemap.xml",
                    SITE.rstrip("/") + "/sitemap_index.xml"):
        try:
            root = ET.fromstring(fetch(sitemap))
            for el in root.iter():
                if el.tag.lower().endswith("loc") and el.text:
                    urls.add(el.text.strip())
        except Exception as exc:
            print(f"[WARN] Sitemap nicht lesbar {sitemap}: {exc}")
    # A small set of likely listing pages as fallback/seed.
    urls.update({
        SITE.rstrip("/") + "/index.php/bands",
        SITE.rstrip("/") + "/index.php/bands/newcomer-2016-2026",
    })
    return sorted(u for u in urls if urlparse(u).netloc == urlparse(SITE).netloc)

def clean_artist(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"\s*[|–—-]\s*(Nachtfragment.*|Dark Music.*)$", "", text, flags=re.I)
    text = text.strip(" |–—-:\t")
    if not text or len(text) < 2 or len(text) > 90: return None
    if re.search(r"(startseite|impressum|datenschutz|kontakt|cookie|sitemap|nächste seite|weiterlesen)", text, re.I):
        return None
    if text.lower() in {"bands", "artists", "nachtfragment", "newcomer 2016–2026", "newcomer 2016-2026"}:
        return None
    return text

def discover_artists():
    found = {}
    for url in site_urls():
        # Focus on likely artist/band pages, but allow the newcomer directory.
        path = urlparse(url).path.lower()
        likely = any(x in path for x in ("/bands/", "/artist/", "/artists/", "/band/")) or "newcomer" in path
        if not likely: continue
        try:
            parser = PageParser()
            parser.feed(fetch(url).decode("utf-8", errors="replace"))
            title = parser.meta.get("og:title") or (parser.h1_text and " ".join(parser.h1_text)) or " ".join(parser.title_text)
            artist = clean_artist(title)
            if artist:
                found[artist.casefold()] = {"name": artist, "nachtfragment_url": url}
        except Exception as exc:
            print(f"[WARN] Seite übersprungen {url}: {exc}")
    # Preserve manually curated aliases/links and previously discovered artists
    old = load_json(ARTISTS_PATH, {"updated_at": None, "artists": []})
    for item in old.get("artists", []):
        if isinstance(item, dict) and item.get("name"):
            found.setdefault(item["name"].casefold(), item)
    artists = sorted(found.values(), key=lambda x: x["name"].casefold())
    save_json(ARTISTS_PATH, {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": SITE,
        "count": len(artists),
        "artists": artists
    })
    print(f"[INFO] Artists erfasst: {len(artists)}")
    return artists

def serpapi_search(artist):
    from urllib.parse import urlencode
    params = {
        "engine": "google",
        "q": f'"{artist}" (concert OR tour OR live OR gig OR festival) 2026 OR 2027',
        "api_key": SERPAPI_KEY,
        "num": 10,
        "hl": "en",
    }
    url = "https://serpapi.com/search.json?" + urlencode(params)
    try:
        return json.loads(fetch(url).decode("utf-8"))
    except Exception as exc:
        print(f"[WARN] Suche fehlgeschlagen für {artist}: {exc}")
        return {}

def main():
    artists = discover_artists()
    if not SERPAPI_KEY:
        print("[WARN] SERPAPI_KEY fehlt. Künstlerliste aktualisiert; Konzertsuche übersprungen.")
        return
    now = date.today()
    candidates = []
    for artist in artists:
        result = serpapi_search(artist["name"])
        for item in result.get("organic_results", []):
            link = item.get("link", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            text = f"{title} {snippet}"
            # Only collect plausible live-event results; never auto-label as confirmed.
            if not re.search(r"\b(concert|tour|live|gig|festival|tickets?|performing|show)\b", text, re.I):
                continue
            if not link.startswith("http"): continue
            candidates.append({
                "artist": artist["name"],
                "nachtfragment_url": artist.get("nachtfragment_url"),
                "title": title,
                "snippet": snippet,
                "source_url": link,
                "status": "needs_review",
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "date": None,
                "venue": None,
                "city": None,
                "note": "Suchtreffer – Datum, Ort und Veranstaltung vor Veröffentlichung prüfen."
            })
        time.sleep(1.0)
    # Stable deduplication by artist + source URL
    unique = {}
    for item in candidates:
        unique[(item["artist"].casefold(), item["source_url"].rstrip("/").casefold())] = item
    candidates = sorted(unique.values(), key=lambda x: (x["artist"].casefold(), x["title"].casefold()))
    save_json(CANDIDATES_PATH, {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(candidates),
        "candidates": candidates
    })
    # Preserve manually confirmed events; don't publish raw search results.
    previous = load_json(CONCERTS_PATH, {"events": []})
    confirmed = [e for e in previous.get("events", []) if e.get("status") == "confirmed"]
    save_json(CONCERTS_PATH, {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Nachtfragment Concert Discovery",
        "count": len(confirmed),
        "events": confirmed
    })
    print(f"[INFO] Kandidaten: {len(candidates)}; bestätigte Termine beibehalten: {len(confirmed)}")

if __name__ == "__main__":
    main()
