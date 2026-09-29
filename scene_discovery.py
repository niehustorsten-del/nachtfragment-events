#!/usr/bin/env python3
# Nachtfragment Scene Discovery
# Ergänzt die bestehende Event-Discovery um Clubs, Bars, Shops und Szene-Veranstalter.
# Keine zusätzlichen Python-Pakete erforderlich.

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

DB_FILE = DATA / "nachtfragment.json"
CANDIDATES_FILE = DATA / "candidates.json"
CHANGES_FILE = DATA / "changes.json"
SCENE_CANDIDATES_FILE = DATA / "scene_candidates.json"
SCENE_CHANGES_FILE = DATA / "scene_changes.json"
GEOCACHE_FILE = DATA / "geocache.json"

QUERY_FILE = ROOT / "scene_search_queries.json"
SOURCE_FILE = ROOT / "scene_discovery_sources.json"

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "").strip()
TODAY = datetime.now(timezone.utc).date().isoformat()
USER_AGENT = "Nachtfragment-Scene-Discovery/1.0 (+https://nachtfragment.de/)"

SCENE_TYPES = {
    "club": ["club", "venue"],
    "bar": ["bar", "venue"],
    "shop": ["shop"],
    "organizer": ["organizer", "venue"],
}

CATEGORY_MAP = {
    "gothic": "gothic_core",
    "goth": "gothic_core",
    "darkwave": "darkwave_wave",
    "dark wave": "darkwave_wave",
    "wave": "darkwave_wave",
    "coldwave": "darkwave_wave",
    "ebm": "ebm_industrial",
    "industrial": "ebm_industrial",
    "dark electro": "dark_electro_futurepop",
    "futurepop": "dark_electro_futurepop",
    "post-punk": "postpunk_deathrock",
    "post punk": "postpunk_deathrock",
    "deathrock": "postpunk_deathrock",
    "dark rock": "alternative_darkrock",
    "alternative": "alternative_darkrock",
}

COUNTRY_CODES = {
    "Germany": "DE", "Austria": "AT", "Switzerland": "CH",
    "France": "FR", "Netherlands": "NL", "Belgium": "BE",
    "United Kingdom": "GB", "Spain": "ES", "Italy": "IT",
    "Denmark": "DK", "Sweden": "SE", "Norway": "NO", "Finland": "FI",
    "Poland": "PL", "Czech Republic": "CZ", "Hungary": "HU",
    "Romania": "RO", "Portugal": "PT", "Serbia": "RS", "Slovenia": "SI",
    "Croatia": "HR", "Greece": "GR", "United States": "US",
    "Canada": "CA", "Australia": "AU", "New Zealand": "NZ",
    "South Africa": "ZA", "Ireland": "IE",
}

def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"WARNING: {path} konnte nicht gelesen werden: {exc}")
        return default

def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

def normalize(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()

def slug(value):
    value = normalize(value).lower()
    value = re.sub(r"[^a-z0-9äöüß]+", "-", value, flags=re.I)
    value = value.strip("-")
    return value[:80] or "scene-entry"

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read(700_000)
        return response.geturl(), content_type, body

def html_text(body):
    text = body.decode("utf-8", errors="ignore")
    text = re.sub(r"(?is)<script.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript.*?</noscript>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize(re.sub(r"&(?:nbsp|amp|quot|#39|lt|gt);", " ", text))

def domain(url):
    return urllib.parse.urlparse(url).netloc.lower().replace("www.", "")

def search_serpapi(query, country=None):
    params = {"engine": "google", "q": query, "api_key": SERPAPI_KEY, "num": 10}
    if country:
        params["gl"] = COUNTRY_CODES.get(country, country.lower()[:2])
        params["hl"] = "en"
    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(params)
    final_url, _, body = fetch(url, timeout=30)
    data = json.loads(body.decode("utf-8", errors="ignore"))
    return data.get("organic_results", [])

def existing_key(item):
    name = normalize(item.get("name")).lower()
    city = normalize(item.get("city")).lower()
    country = normalize(item.get("country") or item.get("country_name")).lower()
    return (name, city, country)

def is_duplicate(item, existing):
    key = existing_key(item)
    if item.get("id") and any(str(x.get("id")) == str(item["id"]) for x in existing):
        return True
    return key in {existing_key(x) for x in existing if isinstance(x, dict)}

def infer_type(query, title, snippet):
    text = f"{query} {title} {snippet}".lower()
    if any(x in text for x in ["gothic shop", "dark fashion", "goth shop", "alternative shop", "record store"]):
        return "shop"
    if any(x in text for x in ["promoter", "promoterin", "veranstalter", "events by", "event organizer"]):
        return "organizer"
    if any(x in text for x in ["bar", "pub", "lounge"]):
        return "bar"
    if any(x in text for x in ["club", "nightclub", "nachtclub", "venue", "discotheque"]):
        return "club"
    return None

def infer_categories(text):
    low = text.lower()
    found = []
    for needle, category in CATEGORY_MAP.items():
        if needle in low and category not in found:
            found.append(category)
    return found

def extract_city_country(text):
    # Absichtlich konservativ: lieber keine Stadt als eine erfundene Stadt.
    patterns = [
        r"\b(?:in|at|from|aus|in)\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß' .-]{2,40})\s*,\s*([A-ZÄÖÜ][A-Za-zÄÖÜäöüß .-]{2,40})\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return normalize(m.group(1)), normalize(m.group(2))
    return None, None

def parse_result(result, query, country_hint):
    title = normalize(result.get("title"))
    link = normalize(result.get("link"))
    snippet = normalize(result.get("snippet"))
    if not title or not link:
        return None

    typ = infer_type(query, title, snippet)
    if not typ:
        return None

    try:
        final_url, content_type, body = fetch(link)
        text = html_text(body)
        if len(text) < 80:
            return None
    except Exception:
        return None

    combined = f"{title} {snippet} {text[:30000]}"
    cats = infer_categories(combined)

    # Mindest-Szenebezug
    scene_terms = [
        "gothic", "darkwave", "dark wave", "ebm", "industrial",
        "post-punk", "post punk", "deathrock", "dark electro",
        "futurepop", "alternative", "cyber", "batcave"
    ]
    scene_hits = sum(1 for term in scene_terms if term in combined.lower())
    if scene_hits < 1:
        return None

    city, country_from_text = extract_city_country(combined[:30000])
    country = country_from_text or country_hint
    if not country:
        return None

    # Für physische Orte muss zumindest ein Ortsindikator vorhanden sein.
    location_terms = ["address", "adresse", "straße", "strasse", "street", "road",
                       "venue", "club", "bar", "shop", "location", "location:", "in "]
    location_hit = any(x in combined.lower() for x in location_terms)
    if typ != "organizer" and not location_hit:
        return None

    score = 35
    score += min(scene_hits * 8, 32)
    if city:
        score += 12
    if country:
        score += 8
    if any(x in combined.lower() for x in ["official website", "contact", "impressum", "kontakt"]):
        score += 8
    if typ in ("club", "bar") and any(x in combined.lower() for x in ["darkwave", "gothic", "ebm", "industrial"]):
        score += 8
    if typ == "shop" and any(x in combined.lower() for x in ["gothic", "dark fashion", "alternative"]):
        score += 8

    score = min(score, 100)
    status = "green" if score >= 78 and city else "yellow"

    name = re.sub(r"\s*[-|–].*$", "", title).strip() or title
    categories = cats or ["alternative_darkrock"]
    types = SCENE_TYPES[typ]

    item = {
        "id": "scene-" + hashlib.sha1(f"{name}|{city}|{country}".encode("utf-8")).hexdigest()[:12],
        "name": name,
        "city": city,
        "country": country,
        "country_name": country,
        "type": types,
        "categories": categories,
        "description": f"Automatisch entdeckter Szene-Ort für die Nachtfragment-Datenbank ({typ}).",
        "lat": None,
        "lng": None,
        "url": final_url,
        "verified": status == "green",
        "verified_date": TODAY if status == "green" else None,
        "audit_status": status,
        "audit_label": "🟢 aktuell bestätigt" if status == "green" else "🟡 zu prüfen",
        "audit_note": f"Auto-Discovery: Score {score}/100; {scene_hits} Szene-Begriffe erkannt.",
        "place_type": typ,
        "is_physical": typ != "organizer",
        "map_category": typ if typ in ("club", "shop") else "venue",
        "map_marker_type": typ if typ in ("club", "shop") else "venue",
        "map_visible": status == "green",
        "icon_category": typ if typ in ("club", "shop") else "venue",
        "source_url": final_url,
        "discovery_score": score,
        "discovered_by": "scene-discovery",
        "discovered_date": TODAY,
    }
    return item

def geocode(item, cache):
    city = normalize(item.get("city"))
    country = normalize(item.get("country") or item.get("country_name"))
    if not city or not country:
        return
    key = f"{city}|{country}".lower()
    if key in cache:
        item["lat"], item["lng"] = cache[key]["lat"], cache[key]["lng"]
        return

    params = urllib.parse.urlencode({
        "q": f"{city}, {country}",
        "format": "json",
        "limit": 1,
    })
    url = "https://nominatim.openstreetmap.org/search?" + params
    try:
        _, _, body = fetch(url, timeout=20)
        results = json.loads(body.decode("utf-8", errors="ignore"))
        if results:
            lat = float(results[0]["lat"])
            lng = float(results[0]["lon"])
            cache[key] = {"lat": lat, "lng": lng, "checked": TODAY}
            item["lat"], item["lng"] = lat, lng
            time.sleep(1.1)
    except Exception as exc:
        print(f"WARNING: Geocoding fehlgeschlagen für {city}, {country}: {exc}")

def main():
    if not SERPAPI_KEY:
        print("SERPAPI_KEY fehlt – Scene Discovery wird übersprungen.")
        return

    db = load_json(DB_FILE, [])
    if not isinstance(db, list):
        raise SystemExit("FEHLER: data/nachtfragment.json muss eine Top-Level-Liste sein.")

    queries = load_json(QUERY_FILE, [])
    sources = load_json(SOURCE_FILE, {})
    if not isinstance(queries, list):
        raise SystemExit("FEHLER: scene_search_queries.json muss eine Liste sein.")

    candidates = load_json(SCENE_CANDIDATES_FILE, [])
    changes = load_json(SCENE_CHANGES_FILE, [])
    geocache = load_json(GEOCACHE_FILE, {})

    existing = list(db)
    seen_urls = set()
    new_green = []
    new_yellow = []

    for entry in queries:
        query = normalize(entry.get("query"))
        country = normalize(entry.get("country"))
        if not query:
            continue

        # Quellen aus der Konfiguration können an die Suche angehängt werden.
        source_domains = entry.get("domains", [])
        for d in source_domains:
            if d:
                query += f" site:{d}"

        print(f"Suche: {query} [{country or 'global'}]")
        try:
            results = search_serpapi(query, country)
        except Exception as exc:
            print(f"WARNING: SerpApi: {exc}")
            continue

        for result in results:
            link = normalize(result.get("link"))
            if not link or link in seen_urls:
                continue
            seen_urls.add(link)

            item = parse_result(result, query, country)
            if not item:
                continue

            if is_duplicate(item, existing) or is_duplicate(item, new_green):
                continue

            if item["audit_status"] == "green":
                geocode(item, geocache)
                if item.get("lat") is not None:
                    new_green.append(item)
                else:
                    item["audit_status"] = "yellow"
                    item["audit_label"] = "🟡 zu prüfen"
                    item["map_visible"] = False
                    new_yellow.append(item)
            else:
                new_yellow.append(item)

    # Kandidaten deduplizieren
    candidate_keys = {existing_key(x) for x in candidates if isinstance(x, dict)}
    for item in new_yellow:
        if existing_key(item) not in candidate_keys:
            candidates.append(item)
            candidate_keys.add(existing_key(item))

    # Sichere Treffer veröffentlichen
    if new_green:
        db.extend(new_green)

    for item in new_green:
        changes.append({
            "date": TODAY,
            "action": "scene_discovery_add",
            "id": item["id"],
            "name": item["name"],
            "city": item["city"],
            "country": item["country"],
            "place_type": item["place_type"],
            "score": item["discovery_score"],
            "url": item["url"],
        })

    save_json(DB_FILE, db)
    save_json(SCENE_CANDIDATES_FILE, candidates)
    save_json(SCENE_CHANGES_FILE, changes)
    save_json(GEOCACHE_FILE, geocache)

    # Auch in das bestehende Änderungsprotokoll schreiben, falls vorhanden.
    existing_changes = load_json(CHANGES_FILE, [])
    if isinstance(existing_changes, list):
        for item in new_green:
            existing_changes.append({
                "date": TODAY,
                "action": "scene_discovery_add",
                "id": item["id"],
                "name": item["name"],
                "city": item["city"],
                "country": item["country"],
                "place_type": item["place_type"],
                "score": item["discovery_score"],
            })
        save_json(CHANGES_FILE, existing_changes)

    print()
    print(f"Scene Discovery fertig: {len(new_green)} veröffentlicht, {len(new_yellow)} Kandidaten.")
    print(f"Datenbank: {len(db)} Einträge")
    print(f"Kandidaten: {len(candidates)}")
    print(f"Quellenkonfiguration: {len(sources.get('preferred_domains', []))} bevorzugte Domains")

if __name__ == "__main__":
    main()
