#!/usr/bin/env python3
"""Discover recent public artist news without API keys; findings are review-only."""
from __future__ import annotations
import hashlib, html, json, re, time, os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
ARTISTS_FILE = ROOT / "data" / "artists.json"
OUTPUT_FILE = ROOT / "data" / "artist-news-candidates.json"
SOURCE_CONFIG = ROOT / "artist_news_sources.json"
UA = "Mozilla/5.0 (compatible; Nachtfragment-NewsBot/1.0; +https://nachtfragment.de)"
MAX_ARTISTS = max(0, int(os.getenv("ARTIST_NEWS_MAX_ARTISTS", "0")))  # 0 = alle Artists
MAX_PER_ARTIST = 12
DAYS = 45
MUSIC_WORDS = re.compile(r"\b(music|musician|band|singer|album|ep|lp|new single|single [‘“']|song|track|release|released|premiere|music video|tour|festival|concert|gig|darkwave|gothic|post.?punk|industrial|ebm|synth|coldwave|new wave|record label|remix|lineup|line-up|auftritt|konzert|veröffentlich|musikvideo|tournee|dark-pop)\b", re.I)
NOISE = re.compile(r"\b(weather|stock market|share price|football|soccer|basketball|cricket|politician|election|obituary|tribute act|cover band|customs seized|tax authority)\b", re.I)

def load_json(path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return default

def norm(s):
    return " ".join(re.findall(r"[^\W_]+", html.unescape(str(s or "")).casefold(), flags=re.UNICODE))

def contains_artist(name, text):
    n, t = norm(name), norm(text)
    return bool(n and t and re.search(r"(?<![\w])" + re.escape(n).replace(r"\ ", r"\s+") + r"(?![\w])", t))

def clean_url(url):
    url = html.unescape(str(url or "")).strip()
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.netloc: return ""
    return url.split("#", 1)[0]

def fetch_xml(url):
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    try:
        with urlopen(req, timeout=18) as response: return response.read(2_000_000)
    except Exception as exc:
        print("FEED_ERROR", url[:130], type(exc).__name__)
        return b""

def text_of(node, names):
    for name in names:
        el = node.find(name)
        if el is not None: return " ".join("".join(el.itertext()).split())
    return ""

def parse_feed(raw, feed_name):
    if not raw: return []
    try: root = ET.fromstring(raw)
    except ET.ParseError: return []
    items = []
    for node in root.findall(".//item"):
        source = node.find("source")
        publisher = " ".join("".join(source.itertext()).split()) if source is not None else feed_name
        items.append({"title":text_of(node,["title"]),"url":clean_url(text_of(node,["link"])),"summary":text_of(node,["description"]),"published":text_of(node,["pubDate"]),"publisher":publisher or feed_name})
    atom = "{http://www.w3.org/2005/Atom}"
    for node in root.findall(".//" + atom + "entry"):
        link_el = node.find(atom + "link")
        items.append({"title":text_of(node,[atom+"title"]),"url":clean_url(link_el.attrib.get("href","") if link_el is not None else ""),"summary":text_of(node,[atom+"summary",atom+"content"]),"published":text_of(node,[atom+"published",atom+"updated"]),"publisher":feed_name})
    return items

def parse_date(value):
    value = str(value or "").strip()
    if not value: return ""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        try:
            dt = datetime.fromisoformat(value.replace("Z","+00:00"))
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
        except Exception: return ""

def category(text):
    t=text.casefold()
    if re.search(r"\b(interview|conversation|talks? to|im gespräch)\b",t): return "Interview"
    if re.search(r"\b(video|visualizer|clip|music video)\b",t): return "Video"
    if re.search(r"\b(tour|festival|line.?up|concert|gig|live dates|konzert)\b",t): return "Tour / Live"
    if re.search(r"\b(album|lp|ep|single|release|released|premiere|track|song)\b",t): return "Release"
    return "News"

def main():
    source=load_json(ARTISTS_FILE,{})
    artists=source.get("artists",[]) if isinstance(source,dict) else []
    now=datetime.now(timezone.utc); cutoff=now-timedelta(days=DAYS)
    results=[]; seen=set(); valid=[]
    for row in artists:
        if not isinstance(row,dict): continue
        name=str(row.get("name") or row.get("artist") or "").strip()
        page=str(row.get("nachtfragment_url") or row.get("url") or "").strip()
        match=re.search(r"/index\.php/artists/([a-z0-9-]+)/?$",urlsplit(page).path,re.I)
        if not match or not name: continue
        name=re.sub(r"\s*[–-]\s*(Porträt|Portrait|Playlist|Linkliste|Zwischen Darkwave.*|Zwischen .*).*$","",name,flags=re.I).strip()
        name=re.sub(r"\s+Playlist$","",name,flags=re.I).strip()
        words=name.split()
        if len(words)>=2 and len(words)%2==0:
            half=len(words)//2
            if [w.casefold() for w in words[:half]]==[w.casefold() for w in words[half:]]: name=" ".join(words[:half])
        if match.group(1).lower()=="nctrl-music": name="N/CTRL"
        if match.group(1).lower()=="ist-ist": name="IST IST"
        if re.search(r"newcomer|linkliste|weblinks|rezension|review|top\s*50|verzeichnis",name,re.I): continue
        valid.append((name,match.group(1).lower()))
    selected = valid[:MAX_ARTISTS] if MAX_ARTISTS else valid
    source_config = load_json(SOURCE_CONFIG, {})
    domain_groups = source_config.get("search_domain_groups", [])
    # Direct publication feeds are fetched once, then matched against every artist.
    direct_items = []
    for feed in source_config.get("direct_feeds", []):
        for item in parse_feed(fetch_xml(feed["url"]), feed["name"]):
            direct_items.append(item | {"source": feed["name"]})
        time.sleep(0.3)
    for index,(name,slug) in enumerate(selected,1):
        q=quote_plus('"'+name+'" (music OR band OR album OR single OR interview OR video OR tour)')
        feeds=[("Google News",f"https://news.google.com/rss/search?q={q}+when%3A{DAYS}d&hl=en-US&gl=US&ceid=US:en"),("Bing News",f"https://www.bing.com/news/search?q={q}+when%3A{DAYS}d&format=rss")]
        for group in domain_groups:
            domains = " OR ".join("site:" + d for d in group.get("domains", []))
            if not domains: continue
            targeted = quote_plus(f'"{name}" ({domains})')
            feeds.extend([
                (group.get("name", "Underground search") + " / Google News",
                 f"https://news.google.com/rss/search?q={targeted}+when%3A{DAYS}d&hl=en-US&gl=US&ceid=US:en"),
                (group.get("name", "Underground search") + " / Bing News",
                 f"https://www.bing.com/news/search?q={targeted}+when%3A{DAYS}d&format=rss")
            ])
        artist_items=[]
        candidate_sources = [(item.get("source", item["publisher"]), item) for item in direct_items]
        for feed_name,feed_url in feeds:
            candidate_sources.extend((feed_name, item) for item in parse_feed(fetch_xml(feed_url),feed_name))
            time.sleep(0.15)
        for feed_name,item in candidate_sources:
                title=html.unescape(item["title"]).strip()
                summary=html.unescape(re.sub(r"<[^>]+>"," ",item["summary"])).strip()
                full=title+" "+summary
                if not title or not item["url"] or not contains_artist(name,full): continue
                if not MUSIC_WORDS.search(title) or NOISE.search(title): continue
                title_fold=title.casefold()
                if "korine fujiwara" in title_fold or "free rein" in title_fold or "james d’arcy" in title_fold or "james d'arcy" in title_fold or "d’arcy james" in title_fold or "d'arcy james" in title_fold or "d’arcy street" in title_fold or "d'arcy street" in title_fold or "d’arcy carden" in title_fold or "d'arcy carden" in title_fold or "d’arcy’s march" in title_fold or "d'arcy's march" in title_fold: continue
                if name.casefold()=="customs" and not re.search(r"\b(band|album|ep|new single|song|track|festival|concert|gig|darkwave|gothic|post.?punk|industrial|ebm|synth|coldwave|record label|remix)\b",title,re.I): continue
                published=parse_date(item["published"])
                if not published: continue
                try: dt=datetime.fromisoformat(published)
                except ValueError: continue
                if dt<cutoff or dt>now+timedelta(days=2): continue
                key=(slug,item["url"].split("?",1)[0].casefold())
                if key in seen: continue
                seen.add(key)
                digest=hashlib.sha256((slug+"|"+item["url"]).encode()).hexdigest()[:20]
                artist_items.append({"id":digest,"artist":name,"artist_slug":slug,"title":title[:300],"summary":summary[:700],"date":published,"category":category(full),"publisher":item["publisher"],"url":item["url"],"source":feed_name,"status":"needs_review"})
            time.sleep(0.25)
        artist_items.sort(key=lambda x:x["date"],reverse=True)
        results.extend(artist_items[:MAX_PER_ARTIST])
        print(f"[{index}/{len(selected)}] {name}: {len(artist_items)} Treffer")
        time.sleep(0.2)
    results.sort(key=lambda x:x["date"],reverse=True)
    payload={"updated_at":now.isoformat(timespec="seconds"),"lookback_days":DAYS,"artist_count":len(selected),"candidate_count":len(results),"source_groups":len(domain_groups),"direct_feed_count":len(source_config.get("direct_feeds", [])),"approval_required":True,"items":results}
    OUTPUT_FILE.parent.mkdir(parents=True,exist_ok=True)
    tmp=OUTPUT_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(OUTPUT_FILE)
    print(f"NEWS_DISCOVERY_DONE artists={payload['artist_count']} candidates={len(results)} (none auto-published)")

if __name__=="__main__": main()
