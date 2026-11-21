#!/usr/bin/env python3
"""Nachtfragment Music Charts discovery.

Collects public HTML pages (no RSS, API key, account or paid search service).
Findings are review candidates only: this script never changes the Top 50.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CHART_FILE = ROOT / "data" / "music-charts.json"
OUTPUT_FILE = ROOT / "data" / "music-chart-candidates.json"
UA = "Mozilla/5.0 (compatible; Nachtfragment-MusicCharts/1.0; +https://nachtfragment.de)"
MAX_BYTES = 2_000_000
MAX_ARTICLES_PER_SOURCE = 35
DAYS_BACK = 45
TODAY = date.today()

SOURCES = [
    {"name": "Side-Line", "url": "https://www.side-line.com/", "kind": "editorial"},
    {"name": "Post-Punk.com – New Releases", "url": "https://post-punk.com/category/new-releases/", "kind": "editorial"},
    {"name": "Post-Punk.com – Singles", "url": "https://post-punk.com/category/new-releases/singles/", "kind": "editorial"},
    {"name": "ReGen Magazine", "url": "https://regenmag.com/", "kind": "editorial"},
    {"name": "IDIEY OUDIE", "url": "https://www.idieyoudie.com/", "kind": "editorial"},
    {"name": "Brutal Resonance", "url": "https://www.brutalresonance.com/", "kind": "editorial"},
    {"name": "Obscure Sound", "url": "https://www.obscuresound.com/", "kind": "editorial"},
    {"name": "Dais Records", "url": "https://daisrecords.com/collections/all", "kind": "editorial"},
    {"name": "Dark Entries Records", "url": "https://darkentriesrecords.com/collections/all", "kind": "editorial"},
    {"name": "Manic Depression Records", "url": "https://manicdepressionrecords.com/", "kind": "editorial"},
    {"name": "Mannequin Records", "url": "https://mannequinrecords.com/", "kind": "editorial"},
    {"name": "Bandcamp – Darkwave", "url": "https://bandcamp.com/tag/darkwave?tab=all_releases&s=newest", "kind": "bandcamp"},
    {"name": "Bandcamp – Post-Punk", "url": "https://bandcamp.com/tag/post-punk?tab=all_releases&s=newest", "kind": "bandcamp"},
    {"name": "Bandcamp – Coldwave", "url": "https://bandcamp.com/tag/coldwave?tab=all_releases&s=newest", "kind": "bandcamp"},
    {"name": "Bandcamp – EBM", "url": "https://bandcamp.com/tag/ebm?tab=all_releases&s=newest", "kind": "bandcamp"},
    {"name": "Bandcamp – Industrial", "url": "https://bandcamp.com/tag/industrial?tab=all_releases&s=newest", "kind": "bandcamp"},
    {"name": "Bandcamp – Minimal Synth", "url": "https://bandcamp.com/tag/minimal-synth?tab=all_releases&s=newest", "kind": "bandcamp"},
    {"name": "Bandcamp – Deathrock", "url": "https://bandcamp.com/tag/deathrock?tab=all_releases&s=newest", "kind": "bandcamp"},
    {"name": "Bandcamp – Gothic Rock", "url": "https://bandcamp.com/tag/gothic-rock?tab=all_releases&s=newest", "kind": "bandcamp"},
    {"name": "Bandcamp – Dark Electro", "url": "https://bandcamp.com/tag/dark-electro?tab=all_releases&s=newest", "kind": "bandcamp"},
    {"name": "Detriti Records", "url": "https://detritirecords.bandcamp.com/", "kind": "bandcamp"},
    {"name": "Dark Entries Records", "url": "https://darkentriesrecords.bandcamp.com/", "kind": "bandcamp"},
    {"name": "Mannequin Records", "url": "https://mannequinrecords.bandcamp.com/", "kind": "bandcamp"},
]

GENRES = {
    "Darkwave": r"darkwave|dark wave",
    "Post-Punk": r"post.?punk",
    "Coldwave": r"coldwave|cold wave",
    "Gothic Rock": r"gothic rock|goth rock",
    "EBM": r"\bebm\b|electronic body music",
    "Industrial": r"industrial|power electronics",
    "Dark Electro": r"dark electro|aggrotech",
    "Dark Synth": r"dark synth|darksynth",
    "Synthpop": r"synth.?pop",
    "Minimal Synth": r"minimal synth|minimal wave",
    "Deathrock": r"deathrock|death rock",
    "Dark Pop": r"dark pop",
    "Ethereal": r"ethereal wave|ethereal",
    "Neofolk": r"neofolk|dark folk",
}
RELEASE_WORDS = re.compile(
    r"\b(releases?|released|out now|out today|available now|shares? (?:a |the )?(?:new )?(?:single|track)|"
    r"new single|new track|new album|new ep|debut single|debut ep|debut album|album streaming|"
    r"premieres? (?:a |the )?(?:new )?(?:single|track)|unveils? (?:a |the )?(?:new )?(?:single|track))\b",
    re.I,
)
REISSUE_WORDS = re.compile(r"\b(reissue|re-issue|re-release|rerelease|remaster|remastered|anniversary edition|compilation)\b", re.I)
FUTURE_ANNOUNCEMENT = re.compile(r"\b(announces?|announced|due out|scheduled for|will release|to be released|coming on)\b", re.I)
DATE_PATTERNS = [
    re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b"),
    re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})\b", re.I),
    re.compile(r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\b", re.I),
]
MONTHS = {m.lower(): i for i, m in enumerate(
    ["", "January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"]) if m}

def clean_url(url: str) -> str:
    try:
        p = urlsplit(html.unescape(str(url or "")).strip())
        if p.scheme not in ("http", "https") or not p.netloc:
            return ""
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", urlencode(query), ""))
    except Exception:
        return ""

def fetch(url: str) -> tuple[str, str]:
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"})
    with urlopen(req, timeout=20) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        body = response.read(MAX_BYTES).decode("utf-8", "replace")
        return response.geturl(), body if ("html" in content_type or not content_type) else ""

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.meta = {}
        self._anchor = None
        self._title = False
        self.title = []
        self.text = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag.lower() == "a" and a.get("href"):
            self._anchor = {"href": a["href"], "text": []}
        if tag.lower() == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content"):
                self.meta[key] = a["content"]
        if tag.lower() == "title":
            self._title = True
    def handle_data(self, data):
        value = " ".join(data.split())
        if not value:
            return
        self.text.append(value)
        if self._anchor is not None:
            self._anchor["text"].append(value)
        if self._title:
            self.title.append(value)
    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._anchor is not None:
            item = self._anchor
            item["text"] = " ".join(item["text"]).strip()
            self.links.append(item)
            self._anchor = None
        if tag.lower() == "title":
            self._title = False

def extract_date(text: str) -> str:
    text = html.unescape(text or "")
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        try:
            if pattern is DATE_PATTERNS[0]:
                d = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            elif pattern is DATE_PATTERNS[1]:
                d = date(int(match.group(3)), MONTHS[match.group(1).lower()], int(match.group(2)))
            else:
                d = date(int(match.group(3)), MONTHS[match.group(2).lower()], int(match.group(1)))
            return d.isoformat()
        except ValueError:
            continue
    return ""

def genre_tags(text: str) -> list[str]:
    return [genre for genre, pattern in GENRES.items() if re.search(pattern, text or "", re.I)]

def guess_artist(headline: str) -> str:
    value = re.sub(r"\s+", " ", html.unescape(headline)).strip(" –—-")
    patterns = [
        r"^(.+?)\s+(?:releases?|shares?|unveils?|premieres?)\s+",
        r"^(.+?)\s+returns? with\s+",
        r"^(.+?)\s+(?:release|share|unveil)\s+",
        r"^(?:.*?\b(?:artist|duo|band|outfit|project|act)\s+)(.+?)\s+(?:finds?|explores?|examines?|confronts?|holds?|pushes?|asks?|faces?|returns?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, value, re.I)
        if match:
            guess = match.group(1).strip(" –—-")
            guess = re.sub(r"^(?:mighty\s+)?(?:darkwave\s+|post[- ]?punk\s+|gothic\s+|industrial\s+)?(?:duo|trio|quartet|band|project|act|outfit)\s+", "", guess, flags=re.I)
            if len(guess) > 1 and len(guess) < 100:
                return guess
    return ""

def guess_release(headline: str) -> str:
    match = re.search(r"[“\"'](.+)[”\"']", html.unescape(headline))
    return match.group(1).strip() if match else ""

def parse_article(url: str, publisher: str, source_kind: str) -> dict | None:
    try:
        final_url, body = fetch(url)
    except Exception as exc:
        print("ARTICLE_ERROR", url, type(exc).__name__)
        return None
    if not body:
        return None
    page = PageParser()
    page.feed(body)
    headline = (page.meta.get("og:title") or " ".join(page.title)).strip()
    headline = re.sub(r"\s*[|–-]\s*(Side-Line|Post-Punk\.com|ReGen Magazine).*?$", "", headline, flags=re.I).strip()
    content = " ".join(page.text)
    combined = headline + " " + content[:12000]
    tags = genre_tags(combined)
    if not tags or not RELEASE_WORDS.search(headline + " " + content[:4500]):
        return None
    # Video-only coverage and interviews are not chart releases.
    if re.search(r"\b(interview|conversation|talks? to)\b", headline, re.I):
        return None
    if re.search(r"\bvideo\b", headline, re.I) and not re.search(r"\b(single|track|song|album|ep)\b", headline, re.I):
        return None
    if re.search(r"\b(signs? to|signing to|record deal)\b", headline, re.I):
        return None
    if REISSUE_WORDS.search(headline):
        return None
    if FUTURE_ANNOUNCEMENT.search(headline) and not re.search(r"\b(released|out now|available now|premieres?|shares? (?:a |the )?(?:new )?single)\b", headline, re.I):
        return None

    article_date = (page.meta.get("article:published_time") or page.meta.get("date") or
                    page.meta.get("pubdate") or "")
    article_date = article_date[:10] if re.match(r"20\d{2}-\d{2}-\d{2}", article_date) else extract_date(content[:1800])
    if article_date:
        try:
            d = date.fromisoformat(article_date)
            if d < TODAY - timedelta(days=DAYS_BACK) or d > TODAY + timedelta(days=3):
                return None
        except ValueError:
            article_date = ""

    release_date = ""
    release_match = re.search(
        r"\b(?:released|release|out|available)\b.{0,260}?\b(?:on\s+)?((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d{2}|\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}|20\d{2}-\d{2}-\d{2})",
        content[:9000], re.I | re.S)
    if release_match:
        release_date = extract_date(release_match.group(1))
    artist = guess_artist(headline)
    release = guess_release(headline)
    if not artist or not release:
        return None
    external_links = []
    artist_bandcamp_url = ""
    for link in page.links:
        target = clean_url(urljoin(final_url, link.get("href", "")))
        host = urlsplit(target).netloc.lower()
        path = urlsplit(target).path.lower()
        if not target:
            continue
        if "bandcamp.com" in host:
            if host != "sidelinemag.bandcamp.com" and not artist_bandcamp_url:
                artist_bandcamp_url = target
            if host != "sidelinemag.bandcamp.com" and path != "/" and re.search(r"/(track|album)/", path):
                external_links.append(target)
        elif any(domain in host for domain in ("spotify.com", "music.apple.com", "soundcloud.com")):
            if re.search(r"/(track|album)/", path) or "music.apple.com" in host:
                external_links.append(target)
    primary_release_url = next((u for u in external_links if "bandcamp.com" in urlsplit(u).netloc.lower()), "")
    if not primary_release_url and external_links:
        primary_release_url = external_links[0]
    artwork = page.meta.get("og:image", "")
    key = hashlib.sha256((clean_url(final_url) or url).encode()).hexdigest()[:16]
    return {
        "id": key,
        "artist_guess": artist,
        "release_title_guess": release,
        "headline": headline,
        "genre_tags": tags,
        "release_date": release_date,
        "article_date": article_date,
        "format_guess": "Single / Track" if re.search(r"single|track|song", headline, re.I) else "EP / Album / unklar",
        "publisher": publisher,
        "source_url": clean_url(final_url) or clean_url(url),
        "primary_release_url": primary_release_url,
        "artist_bandcamp_url": artist_bandcamp_url,
        "external_release_links": external_links[:8],
        "artwork": clean_url(artwork),
        "status": "needs_editorial_review",
        "verification_note": "Artikel gefunden; Release-Datum und genaue Artist-/Titel-Zuordnung vor Chartaufnahme prüfen."
    }

def bandcamp_candidates(page_url: str, publisher: str) -> list[dict]:
    try:
        final_url, body = fetch(page_url)
    except Exception as exc:
        print("SOURCE_ERROR", page_url, type(exc).__name__)
        return []
    if not body:
        return []
    parser = PageParser()
    parser.feed(body)
    out = []
    seen = set()
    for link in parser.links:
        target = clean_url(urljoin(final_url, link["href"]))
        if "bandcamp.com" not in urlsplit(target).netloc:
            continue
        path = urlsplit(target).path.strip("/")
        if not (path.endswith("/album") or path.endswith("/track") or "/album/" in path or "/track/" in path):
            continue
        if target in seen:
            continue
        seen.add(target)
        title = link["text"]
        if not title or len(title) < 2:
            continue
        out.append({
            "id": hashlib.sha256(target.encode()).hexdigest()[:16],
            "artist_guess": "",
            "release_title_guess": title,
            "headline": title,
            "genre_tags": genre_tags(title + " " + publisher),
            "release_date": "",
            "article_date": "",
            "format_guess": "Bandcamp Release – bitte prüfen",
            "publisher": publisher,
            "source_url": target,
            "artwork": "",
            "status": "needs_editorial_review",
            "verification_note": "Direkter Bandcamp-Release-Link gefunden; Artist, Genre und Veröffentlichungsdatum prüfen."
        })
    return out

def load_existing_chart_ids() -> set[str]:
    try:
        data = json.loads(CHART_FILE.read_text(encoding="utf-8"))
        return {
            (str(row.get("artist", "")).strip().casefold() + "|" +
             str(row.get("title", "")).strip().casefold())
            for row in data.get("tracks", []) if isinstance(row, dict)
        }
    except Exception:
        return set()

def main():
    found = {}
    source_status = []
    for source in SOURCES:
        print("SOURCE", source["name"], source["url"])
        if source["kind"] == "bandcamp":
            items = bandcamp_candidates(source["url"], source["name"])
            for item in items:
                found.setdefault(item["id"], item)
            source_status.append({"name": source["name"], "url": source["url"], "candidates": len(items)})
            time.sleep(0.5)
            continue
        try:
            final_url, body = fetch(source["url"])
            if not body:
                raise RuntimeError("no HTML response")
            parser = PageParser()
            parser.feed(body)
            links = []
            for link in parser.links:
                headline = link["text"]
                target = clean_url(urljoin(final_url, link["href"]))
                if not target or target == clean_url(final_url) or len(headline) < 18:
                    continue
                if urlsplit(target).netloc != urlsplit(final_url).netloc:
                    continue
                if not RELEASE_WORDS.search(headline) and not re.search(r"new releases|single|album|ep|premiere", headline, re.I):
                    continue
                if REISSUE_WORDS.search(headline):
                    continue
                links.append((headline, target))
            # Fetch newest-looking article links only; de-duplicate before detail requests.
            unique = []
            seen_urls = set()
            for headline, target in links:
                if target not in seen_urls:
                    unique.append((headline, target))
                    seen_urls.add(target)
            count = 0
            for headline, target in unique[:MAX_ARTICLES_PER_SOURCE]:
                candidate = parse_article(target, source["name"], source["kind"])
                if candidate:
                    found.setdefault(candidate["id"], candidate)
                    count += 1
                time.sleep(0.15)
            source_status.append({"name": source["name"], "url": source["url"], "article_links": len(unique), "candidates": count})
        except Exception as exc:
            print("SOURCE_ERROR", source["name"], type(exc).__name__, str(exc)[:180])
            source_status.append({"name": source["name"], "url": source["url"], "error": type(exc).__name__})
        time.sleep(0.6)

    existing = load_existing_chart_ids()
    candidates = list(found.values())
    for item in candidates:
        pair = (item.get("artist_guess", "").strip().casefold() + "|" +
                item.get("release_title_guess", "").strip().casefold())
        item["already_in_chart"] = bool(pair != "|" and pair in existing)
    candidates.sort(key=lambda x: (x.get("release_date") or x.get("article_date") or "", x.get("publisher", "")), reverse=True)
    payload = {
        "title": "Nachtfragment Music Charts – Recherchekandidaten",
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "approval_required": True,
        "automatic_publication": False,
        "source_count": len(SOURCES),
        "sources_checked": source_status,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "note": "Recherche aus öffentlichen HTML-Seiten. Kandidaten sind keine bestätigten Chart-Neuzugänge; Veröffentlichungsdatum, Reissue-Status, Artist, Titel und Primärquelle redaktionell prüfen."
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(OUTPUT_FILE)
    print("SOURCES_CHECKED", len(source_status))
    print("CANDIDATES", len(candidates))
    print("OUTPUT", OUTPUT_FILE)

if __name__ == "__main__":
    main()
