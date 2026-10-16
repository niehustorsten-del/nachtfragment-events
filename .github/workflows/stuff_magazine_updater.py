#!/usr/bin/env python3
"""Conservative weekly discovery for Nachtfragment Stuff and Magazine."""
from __future__ import annotations
import json, os, re, sys, time
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse
import requests
from bs4 import BeautifulSoup

ROOT = os.path.abspath(os.path.dirname(__file__))
STUFF_PATH = os.path.join(ROOT, "Stuff", "nachtfragment-stuff.json")
MAG_PATH = os.path.join(ROOT, "Magazine", "nachtfragment-magazine.json")
QUERIES_PATH = os.path.join(ROOT, "stuff_magazine_queries.json")
REVIEW_PATH = os.path.join(ROOT, "data", "stuff-magazine-review.json")
TODAY = datetime.now(timezone.utc).date().isoformat()
UA = "NachtfragmentDirectoryBot/1.0 (+https://nachtfragment.de)"
TIMEOUT = 15
MAX_PER_QUERY = 8

BLOCKED_HOSTS = {
    "facebook.com", "instagram.com", "tiktok.com", "pinterest.com", "youtube.com",
    "youtu.be", "reddit.com", "wikipedia.org", "amazon.com", "ebay.com",
    "etsy.com", "bandcamp.com", "soundcloud.com", "spotify.com", "x.com",
    "twitter.com", "linkedin.com"
}
GENRE_TERMS = [
    "goth", "gothic", "darkwave", "post-punk", "post punk", "industrial", "ebm",
    "coldwave", "deathrock", "synthpop", "synth-pop", "dark electro", "alternative",
    "alternative fashion", "witch", "blackwork", "dark art", "tattoo", "bijoux",
    "schmuck", "jewelry", "jewellery", "handmade", "record label", "music label"
]
MAG_TERMS = [
    "magazine", "webzine", "zine", "music news", "reviews", "review", "interviews",
    "interview", "album review", "music magazine", "online magazine", "rezension",
    "rezensionen", "interviews", "musikmagazin", "webmagazin"
]
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA})

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json_atomic(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)

def norm_url(url):
    try:
        p = urlparse((url or "").strip())
        if p.scheme not in ("http", "https") or not p.hostname:
            return ""
        host = p.hostname.lower()
        if host.startswith("www."):
            host = host[4:]
        path = re.sub(r"/+$", "", p.path or "")
        return urlunparse(("https", host, path, "", "", ""))
    except Exception:
        return ""

def host_of(url):
    try:
        h = (urlparse(url).hostname or "").lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""

def is_blocked(url):
    host = host_of(url)
    return any(host == b or host.endswith("." + b) for b in BLOCKED_HOSTS)

def plain(text):
    return re.sub(r"\s+", " ", (text or "")).strip().lower()

def fetch_page(url):
    try:
        r = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", "").lower():
            return None
        if is_blocked(r.url):
            return None
        soup = BeautifulSoup(r.text[:1_500_000], "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        desc = ""
        meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
        if meta:
            desc = meta.get("content", "")
        body = soup.get_text(" ", strip=True)[:120000]
        canonical = soup.find("link", rel="canonical")
        final_url = canonical.get("href") if canonical and canonical.get("href") else r.url
        return {"url": r.url, "canonical": final_url, "title": title, "description": desc, "text": body, "soup": soup}
    except Exception:
        return None

def serp_search(api_key, query):
    try:
        r = SESSION.get("https://serpapi.com/search.json", params={
            "engine": "google", "q": query, "api_key": api_key, "num": MAX_PER_QUERY
        }, timeout=TIMEOUT)
        r.raise_for_status()
        payload = r.json()
        return payload.get("organic_results", []) or []
    except Exception as exc:
        print(f"SEARCH_ERROR query={query!r}: {exc}")
        return []

def relevance_score(page, item_type, category=""):
    text = plain(" ".join([page.get("title",""), page.get("description",""), page.get("text","")]))
    terms = MAG_TERMS if item_type == "magazine" else GENRE_TERMS
    found = [t for t in terms if t in text]
    # Exclude pages whose relevance is only a generic keyword in a footer.
    if item_type == "magazine":
        editorial = sum(1 for t in MAG_TERMS if t in text)
        scene = sum(1 for t in ["gothic","darkwave","post-punk","industrial","ebm","synthpop","coldwave","deathrock"] if t in text)
        return editorial, scene, found
    scene = sum(1 for t in ["gothic","goth","darkwave","post-punk","industrial","ebm","coldwave","deathrock","alternative","witch","dark art","blackwork"] if t in text)
    product = sum(1 for t in ["shop","store","jewelry","jewellery","schmuck","clothing","fashion","tattoo","artist","record label","records","label","handmade","boutique","design","music"] if t in text)
    return scene, product, found

def infer_country(url, query_meta, snippet):
    # Keep the search's target country only when the domain or page evidence supports it.
    country = query_meta.get("country", "International")
    suffixes = {
        "Germany": (".de",), "Austria": (".at",), "Switzerland": (".ch",),
        "Netherlands": (".nl",), "Belgium": (".be",), "France": (".fr",),
        "Sweden": (".se",), "Denmark": (".dk",), "United Kingdom": (".uk", ".co.uk"),
    }
    host = host_of(url)
    if any(host.endswith(s) for s in suffixes.get(country, ())):
        return country
    text = plain(snippet + " " + url)
    hints = {
        "Germany": ["germany","deutschland","german","berlin","hamburg","köln","cologne","leipzig","hannover","münchen","munich"],
        "Austria": ["austria","österreich","vienna","wien","graz","linz","innsbruck"],
        "Switzerland": ["switzerland","schweiz","zürich","zurich","basel","bern","geneva"],
        "Netherlands": ["netherlands","niederlande","amsterdam","rotterdam","utrecht"],
        "Belgium": ["belgium","belgië","belgique","brussels","brüssel","antwerp","gent"],
        "France": ["france","français","paris","lyon","marseille","lille"],
        "Sweden": ["sweden","sverige","stockholm","göteborg","malmö"],
        "Denmark": ["denmark","danmark","copenhagen","københavn"],
        "United Kingdom": ["united kingdom","england","scotland","wales","london","manchester","bristol"],
    }
    if any(h in text for h in hints.get(country, [])):
        return country
    return "International"

def date_evidence(page):
    text = page.get("text", "")
    dates = re.findall(r"\b20(?:2[4-9]|3\d)\b", text)
    if any(int(d) >= datetime.now(timezone.utc).year - 1 for d in dates):
        return True
    soup = page.get("soup")
    if soup:
        for tag in soup.find_all(["time", "meta"]):
            value = " ".join(str(tag.get(a, "")) for a in ["datetime","content","property","name"])
            m = re.search(r"20(?:2[4-9]|3\d)", value)
            if m and int(m.group(0)) >= datetime.now(timezone.utc).year - 1:
                return True
    return False

def main():
    api_key = os.environ.get("SERPAPI_KEY", "").strip()
    if not api_key:
        print("SERPAPI_KEY fehlt; keine Dateien geändert.")
        return 2
    for p in (STUFF_PATH, MAG_PATH, QUERIES_PATH):
        if not os.path.isfile(p):
            print(f"Pflichtdatei fehlt: {os.path.relpath(p, ROOT)}; Abbruch ohne Änderungen.")
            return 2
    stuff = load_json(STUFF_PATH)
    magazine = load_json(MAG_PATH)
    config = load_json(QUERIES_PATH)
    if not isinstance(stuff.get("entries"), list) or not isinstance(magazine.get("magazines"), list):
        print("JSON-Schema unerwartet; Abbruch ohne Änderungen.")
        return 2

    existing_stuff = {norm_url(x.get("url","")) for x in stuff["entries"] if x.get("url")}
    existing_stuff_names = {plain(x.get("name","")) for x in stuff["entries"] if x.get("name")}
    existing_mag = {norm_url(x.get("website","")) for x in magazine["magazines"] if x.get("website")}
    existing_mag_names = {plain(x.get("name","")) for x in magazine["magazines"] if x.get("name")}
    review = []
    added_stuff = []
    added_mag = []
    searched = 0
    visited = set()

    for q in config.get("queries", []):
        query = q.get("query", "").strip()
        kind = q.get("type", "")
        if not query or kind not in ("stuff", "magazine"):
            continue
        results = serp_search(api_key, query)
        searched += 1
        for result in results:
            raw_url = result.get("link", "")
            url = norm_url(raw_url)
            title = (result.get("title") or "").strip()
            snippet = (result.get("snippet") or "").strip()
            if not url or not title or is_blocked(url) or url in visited:
                continue
            visited.add(url)
            known_urls = existing_stuff if kind == "stuff" else existing_mag
            known_names = existing_stuff_names if kind == "stuff" else existing_mag_names
            if url in known_urls or plain(title) in known_names:
                continue
            page = fetch_page(raw_url)
            if not page:
                continue
            final_url = norm_url(page.get("canonical") or page.get("url") or raw_url)
            if not final_url or is_blocked(final_url):
                continue
            if final_url in known_urls:
                continue
            score_a, score_b, found = relevance_score(page, kind, q.get("category",""))
            if kind == "stuff":
                if score_a < 1 or score_b < 1:
                    review.append({"type":kind,"name":title,"url":final_url,"query":query,"reason":"Official page reachable, but category match is not strong enough for automatic publication."})
                    continue
                country = infer_country(final_url, q, snippet + " " + page.get("text","")[:5000])
                entry = {
                    "name": title,
                    "category": [q.get("category", "Gothic Shops")],
                    "country": country,
                    "status": "verified",
                    "tags": q.get("tags", ["Gothic","Alternative"]),
                    "url": final_url
                }
                # Avoid falsely assigning a city from a search snippet.
                added_stuff.append(entry)
                existing_stuff.add(final_url)
                existing_stuff_names.add(plain(title))
            else:
                if score_a < 1 or score_b < 2:
                    review.append({"type":kind,"name":title,"url":final_url,"query":query,"reason":"Site reachable, but music/editorial relevance is not strong enough for automatic publication."})
                    continue
                country = infer_country(final_url, q, snippet + " " + page.get("text","")[:5000])
                active = date_evidence(page)
                entry = {
                    "name": title,
                    "country": country,
                    "language": q.get("language", "Englisch"),
                    "format": ["online"],
                    "status": "aktiv" if active else "archiv / unklar",
                    "focus": q.get("focus", ["Gothic","Darkwave","Post-Punk"]),
                    "website": final_url,
                    "verification": "Automatisch geprüft: Website erreichbar und thematisch passend; Aktivität anhand sichtbarer Datumsangaben bewertet."
                }
                added_mag.append(entry)
                existing_mag.add(final_url)
                existing_mag_names.add(plain(title))
        time.sleep(1.0)

    # Never overwrite the source files unless their original structures are intact.
    if added_stuff:
        stuff["entries"].extend(added_stuff)
        stuff["updated"] = TODAY
        stuff["version"] = str(stuff.get("version","auto")) + "-auto-" + TODAY
        stuff["verification_note"] = (stuff.get("verification_note","").rstrip() + f" Weekly automatic discovery added {len(added_stuff)} reachable, category-matched entries on {TODAY}; uncertain hits are logged separately.").strip()
    if added_mag:
        magazine["magazines"].extend(added_mag)
        magazine["updated"] = TODAY
        magazine["editorial_note"] = (magazine.get("editorial_note","").rstrip() + f" Automatic discovery added {len(added_mag)} reachable, relevant online media on {TODAY}; uncertain hits are logged separately.").strip()

    # Review log is append-only and deduplicated by URL.
    previous_review = []
    if os.path.isfile(REVIEW_PATH):
        try:
            old = load_json(REVIEW_PATH)
            previous_review = old.get("candidates", []) if isinstance(old, dict) else []
        except Exception:
            previous_review = []
    review_by_url = {norm_url(x.get("url","")): x for x in previous_review if x.get("url")}
    for item in review:
        key = norm_url(item.get("url",""))
        if key and key not in review_by_url:
            review_by_url[key] = item
    review_list = list(review_by_url.values())[-500:]
    review_data = {
        "updated": TODAY if review else (load_json(REVIEW_PATH).get("updated", TODAY) if os.path.isfile(REVIEW_PATH) else TODAY),
        "description": "Unsichere Treffer, die nicht automatisch veröffentlicht wurden.",
        "candidates": review_list
    }

    # Validate JSON serializability and write atomically.
    json.dumps(stuff, ensure_ascii=False)
    json.dumps(magazine, ensure_ascii=False)
    # Write the review file only when it is new or genuinely gains candidates.
    previous_urls = {norm_url(x.get("url","")) for x in previous_review if x.get("url")}
    new_review_urls = {norm_url(x.get("url","")) for x in review if x.get("url")}
    if not os.path.isfile(REVIEW_PATH) or new_review_urls - previous_urls:
        save_json_atomic(REVIEW_PATH, review_data)
    if added_stuff:
        save_json_atomic(STUFF_PATH, stuff)
    if added_mag:
        save_json_atomic(MAG_PATH, magazine)
    print(f"SEARCHES={searched} NEW_STUFF={len(added_stuff)} NEW_MAGAZINES={len(added_mag)} REVIEW_CANDIDATES={len(review)}")
    print(f"STUFF_TOTAL={len(stuff['entries'])} MAGAZINE_TOTAL={len(magazine['magazines'])}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
