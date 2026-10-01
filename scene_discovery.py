#!/usr/bin/env python3
"""Nachtfragment Scene Discovery V2: conservative scene discovery."""
from __future__ import annotations
import hashlib, html, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT=Path(__file__).resolve().parent
DATA=ROOT/"data"
DB=DATA/"nachtfragment.json"
CAND=DATA/"scene_candidates.json"
CHANGES=DATA/"scene_changes.json"
CACHE=DATA/"geocache.json"
QUERIES=ROOT/"scene_search_queries.json"
KEY=os.getenv("SERPAPI_KEY","").strip()
UA="Nachtfragment-SceneDiscovery/2.0 (+https://nachtfragment.de/)"
TIMEOUT=15

SCENE={
 "Gothic":["gothic","goth","goth night","gothic night"],
 "Darkwave":["darkwave","dark wave","coldwave","cold wave","wave night"],
 "Industrial":["ebm","electronic body music","industrial","industrial night"],
 "Dark Electro":["dark electro","futurepop","aggrotech","cyber goth","cybergoth"],
 "Post-Punk":["post-punk","post punk","deathrock","dark punk"],
 "Alternative":["dark rock","alternative rock","dark alternative"],
}
VENUE=["goth night","gothic night","darkwave","dark wave","ebm","industrial night",
       "dark electro","futurepop","deathrock","post-punk","cybergoth",
       "goth club","goth bar","dark club","dark party"]
SHOP=["gothic","goth","dark fashion","darkwear","alternative fashion",
      "alternative clothing","punk","industrial","deathrock","cyber goth"]
EVENT=["event","events","party","parties","night","nights","calendar","programme","program","agenda"]
BLOCKED=["wikipedia.org","tripadvisor.","yelp.","eventbrite.","bandsintown.",
         "songkick.","discogs.","last.fm","foursquare.","mapquest.","pinterest."]
EDITORIAL=["magazine","magazin","news","review","reviews","article","artikel","blog","wiki","encyclopedia","dictionary"]

CITIES={
 "Berlin":"Germany","Hamburg":"Germany","Munich":"Germany","München":"Germany","Cologne":"Germany","Köln":"Germany",
 "Frankfurt":"Germany","Leipzig":"Germany","Dresden":"Germany","Stuttgart":"Germany","Hannover":"Germany",
 "Nuremberg":"Germany","Nürnberg":"Germany","Vienna":"Austria","Wien":"Austria","Graz":"Austria",
 "Innsbruck":"Austria","Zurich":"Switzerland","Zürich":"Switzerland","Basel":"Switzerland","Paris":"France",
 "Lyon":"France","Marseille":"France","London":"United Kingdom","Manchester":"United Kingdom","Birmingham":"United Kingdom",
 "Glasgow":"United Kingdom","Edinburgh":"United Kingdom","Dublin":"Ireland","Amsterdam":"Netherlands",
 "Rotterdam":"Netherlands","Brussels":"Belgium","Copenhagen":"Denmark","Stockholm":"Sweden","Oslo":"Norway",
 "Helsinki":"Finland","Warsaw":"Poland","Prague":"Czech Republic","Budapest":"Hungary","Lisbon":"Portugal",
 "Madrid":"Spain","Barcelona":"Spain","Milan":"Italy","Rome":"Italy","Turin":"Italy","Istanbul":"Turkey",
 "New York":"United States","Los Angeles":"United States","Chicago":"United States","Seattle":"United States",
 "Portland":"United States","San Francisco":"United States","Toronto":"Canada","Montreal":"Canada",
 "Sydney":"Australia","Melbourne":"Australia","Brisbane":"Australia","Adelaide":"Australia","Perth":"Australia",
 "Auckland":"New Zealand","Tokyo":"Japan","Osaka":"Japan","Seoul":"South Korea"
}
COUNTRY_NAMES={"Germany":"Deutschland","Austria":"Österreich","Switzerland":"Schweiz","France":"Frankreich",
 "Italy":"Italien","Spain":"Spanien","United Kingdom":"Vereinigtes Königreich","Ireland":"Irland",
 "Netherlands":"Niederlande","Belgium":"Belgien","Denmark":"Dänemark","Sweden":"Schweden","Norway":"Norwegen",
 "Finland":"Finnland","Poland":"Polen","Czech Republic":"Tschechien","Hungary":"Ungarn","Portugal":"Portugal",
 "United States":"USA","Canada":"Kanada","Australia":"Australien","New Zealand":"Neuseeland","Japan":"Japan",
 "South Korea":"Südkorea","Turkey":"Türkei"}

def load(p,d):
    try:return json.loads(p.read_text(encoding="utf-8")) if p.exists() else d
    except Exception:return d
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def clean(s):
    s=html.unescape(s or "")
    s=re.sub(r"<script\b.*?</script>|<style\b.*?</style>"," ",s,flags=re.I|re.S)
    return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",s)).strip()
def norm(u):
    if not u:return ""
    p=urlparse(u)
    if p.scheme not in ("http","https") or not p.netloc:return ""
    return urlunparse((p.scheme,p.netloc.lower().split(":")[0],p.path.rstrip("/") or "/","","",""))
def fetch(u):
    try:
        with urlopen(Request(u,headers={"User-Agent":UA,"Accept-Language":"en,de;q=0.8"}),timeout=TIMEOUT) as r:
            return clean(r.read().decode("utf-8","ignore"))[:180000]
    except (HTTPError,URLError,TimeoutError,ValueError):return ""
def serp(q):
    u="https://serpapi.com/search.json?engine=google&q="+quote(q)+"&num=10&api_key="+quote(KEY)
    with urlopen(Request(u,headers={"User-Agent":UA}),timeout=TIMEOUT) as r:return json.loads(r.read().decode())
def scene_hits(t):
    l=t.lower(); return [k for k,v in SCENE.items() if any(x in l for x in v)]
def infer_type(t):
    l=t.lower()
    if any(x in l for x in SHOP) and any(x in l for x in ["shop","store","clothing","fashion","products","cart","collections"]):return "shop"
    if any(x in l for x in ["promoter","promoters","promotions","veranstalter","event organizer","event organiser"]) and any(x in l for x in EVENT):return "organizer"
    if any(x in l for x in ["club","nightclub","night club","discotheque","venue","dancefloor","dance floor"]) and any(x in l for x in VENUE):return "club"
    if any(x in l for x in ["goth bar","dark bar","alternative bar","bar","pub","lounge"]) and any(x in l for x in VENUE):return "bar"
    return ""
def city_country(t,hint):
    for city,country in sorted(CITIES.items(),key=lambda x:-len(x[0])):
        if re.search(r"(?<!\w)"+re.escape(city)+r"(?!\w)",t,re.I) and (not hint or country.lower()==hint.lower()):
            return city,country
    return "",hint
def address(t):
    pats=[r"(?:address|adresse|location|standort|find us|visit us)\s*[:\-]\s*([^.;|]{10,180})",
          r"\b\d{1,5}\s+[A-Za-zÄÖÜäöüß0-9.' -]{3,80}(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Boulevard|Blvd|Way|Strasse|Straße|Gasse|Weg)\b[^.;|]{0,80}",
          r"\b[A-Za-zÄÖÜäöüß0-9.' -]{3,80}\s+(?:Strasse|Straße|Gasse|Street|Road|Avenue|Boulevard)\s+\d{1,5}\b[^.;|]{0,80}"]
    for p in pats:
        m=re.search(p,t,re.I)
        if m:return re.sub(r"\s+"," ",m.group(1) if m.lastindex else m.group(0)).strip(" ,.-")
    return ""
def online_only(t):
    l=t.lower()
    return any(x in l for x in ["online shop","online store","shop online","worldwide shipping","shipping worldwide"]) and not any(x in l for x in ["store locations","our stores","find a store","shop address","visit us","retail store"])
def score(kind,t,city,addr,cats):
    l=t.lower(); signals=sum(any(x in l for x in v) for v in SCENE.values())
    s=min(40,signals*8)+(12 if city else 0)+(12 if addr else 0)+(10 if cats else 0)
    if kind=="shop":s+=(15 if sum(x in l for x in SHOP)>=2 else 0)+(8 if any(x in l for x in ["cart","products","collections"]) else 0)
    elif kind in ("club","bar"):s+=(18 if any(x in l for x in VENUE) else 0)+(8 if any(x in l for x in EVENT) else 0)
    else:s+=(18 if any(x in l for x in EVENT) else 0)+(10 if any(x in l for x in ["promoter","promotions","organizer","veranstalter"]) else 0)
    if any(x in l for x in EDITORIAL):s-=25
    return max(0,min(100,s))
def dkey(n,c,co):return (re.sub(r"\W+","",n.lower()),re.sub(r"\W+","",c.lower()),co.lower())
def make_id(n,c,co):
    raw=f"{n}-{c}-{co}".lower(); slug=re.sub(r"[^a-z0-9]+","-",raw).strip("-")
    return slug[:90] or "scene-"+hashlib.sha1(raw.encode()).hexdigest()[:12]
def geocode(addr,city,country,cache):
    # Never geocode city-only: that creates inaccurate map pins.
    if not addr:return None
    q=", ".join(x for x in [addr,city,country] if x); k=q.lower()
    if k in cache:return cache[k]
    try:
        u="https://nominatim.openstreetmap.org/search?format=json&limit=1&q="+quote(q)
        with urlopen(Request(u,headers={"User-Agent":UA}),timeout=TIMEOUT) as r:a=json.loads(r.read().decode())
        if a:
            v={"lat":float(a[0]["lat"]),"lng":float(a[0]["lon"])};cache[k]=v;time.sleep(1);return v
    except Exception:pass
    return None

def main():
    if not KEY:raise SystemExit("SERPAPI_KEY fehlt")
    db=load(DB,[]); cand=load(CAND,[]); changes=load(CHANGES,[]); cache=load(CACHE,{})
    cfg=load(QUERIES,{"batches":[]})
    if not isinstance(db,list):raise SystemExit("data/nachtfragment.json muss eine Liste sein")
    if not isinstance(cand,list):cand=[]
    if not isinstance(changes,list):changes=[]
    existing={dkey(str(x.get("name","")),str(x.get("city","")),str(x.get("country",""))) for x in db}
    urls={norm(str(x.get("url",""))) for x in db if x.get("url")}
    candkeys={dkey(str(x.get("name","")),str(x.get("city","")),str(x.get("country",""))) for x in cand}
    candurls={norm(str(x.get("url",""))) for x in cand if x.get("url")}
    batches=cfg.get("batches",[])
    if not batches:return
    queries=batches[(datetime.now(timezone.utc).timetuple().tm_yday-1)%len(batches)]
    pub=queued=skip=errors=0
    for qdef in queries:
        q,hint=qdef["query"],qdef.get("country","")
        try:data=serp(q)
        except Exception as e:print("SerpApi:",e);errors+=1;continue
        for item in data.get("organic_results",[])[:10]:
            title=str(item.get("title","")).strip();url=norm(str(item.get("link","")));snippet=str(item.get("snippet",""))
            if not title or not url or any(x in url.lower() for x in BLOCKED):skip+=1;continue
            page=fetch(url); text=f"{title} {snippet} {page}"; cats=scene_hits(text)
            if not cats:skip+=1;continue
            kind=infer_type(text)
            if not kind:skip+=1;continue
            if kind=="shop" and sum(x in text.lower() for x in SHOP)<2:skip+=1;continue
            city,country=city_country(text,hint);country=country or hint;addr=address(text)
            physical=not(kind=="shop" and online_only(text))
            s=score(kind,text,city,addr,cats)
            green=(s>=82 and (not physical or bool(addr)) and (kind=="shop" or bool(city)) and not any(x in text.lower() for x in EDITORIAL))
            coords=geocode(addr,city,country,cache) if green and physical else None
            if green and physical and not coords:green=False
            rec={"id":make_id(title,city,country),"name":title,"city":city,"country":country,
                 "country_name":COUNTRY_NAMES.get(country,country),"type":[kind]+(["venue"] if kind in ("club","bar","organizer") else []),
                 "categories":cats,"url":url,"description":f"Automatisch entdeckter {kind} für die Nachtfragment-Szene.",
                 "verified":green,"verified_date":datetime.now(timezone.utc).date().isoformat(),
                 "audit_status":"green" if green else "yellow",
                 "audit_label":"🟢 aktuell bestätigt" if green else "🟡 zu prüfen",
                 "audit_note":"Automatisch entdeckt; Szenebezug und Standort geprüft." if green else "Automatisch entdeckt; manuelle Prüfung erforderlich.",
                 "source":"SerpApi Scene Discovery V2","discovery_query":q,"scene_score":s,
                 "is_physical":physical,"map_visible":bool(coords)}
            if addr:rec["address"]=addr
            if coords:rec.update(coords)
            k=dkey(rec["name"],rec["city"],rec["country"])
            if k in existing or k in candkeys or url in urls or url in candurls:skip+=1;continue
            if green:
                db.append(rec);existing.add(k);urls.add(url)
                changes.append({"timestamp":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"action":"scene_discovery_add","id":rec["id"],"name":rec["name"],"type":kind});pub+=1
            else:
                cand.append(rec);candkeys.add(k);candurls.add(url);queued+=1
    save(DB,db);save(CAND,cand);save(CHANGES,changes[-2000:]);save(CACHE,cache)
    print(f"Scene Discovery V2: queries={len(queries)} published={pub} candidates={queued} skipped={skip} errors={errors}")
if __name__=="__main__":main()
