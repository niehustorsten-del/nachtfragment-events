from __future__ import annotations
import json, os, re, time, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, parse_qs, urljoin, unquote
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent
BASE="https://nachtfragment.de"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 NachtfragmentFinder/2.0"
S=requests.Session()
S.headers.update({"User-Agent":UA,"Accept-Language":"de,en;q=0.8"})
BAD=("/watch","/reel","/share","/login","/help","/policies","/events","/groups","/marketplace","/gaming","/search")
SKIP=("newcomer","weblinks","linkliste","rezension","top 50","playlist")
SITEMAPS=("/sitemap.xml","/sitemap_index.xml","/sitemap-index.xml",
"/index.php?option=com_osmap&view=xml&id=1","/component/osmap/?view=xml&id=1",
"/index.php?option=com_jmap&view=sitemap")

def get(url):
    try:
        r=S.get(url,timeout=22); r.raise_for_status(); return r
    except Exception as e:
        print("Abruf fehlgeschlagen:",url,str(e)[:180]); return None

def canonical_artist_url(raw):
    try:
        u=urlparse(urljoin(BASE,raw))
        if u.netloc.lower().split(":")[0] not in ("nachtfragment.de","www.nachtfragment.de"): return ""
        m=re.search(r"(/index\.php/artists/[^/?#]+)",u.path,re.I)
        if not m: return ""
        path=m.group(1).rstrip("/")
        if any(x in path.rsplit("/",1)[-1].lower() for x in ("rezension","review","playlist","linkliste","newcomer","top-50","weblinks")): return ""
        return BASE+path
    except Exception: return ""

def collect_sitemap(url, seen, found, depth=0):
    if depth>3 or url in seen: return
    seen.add(url); r=get(url)
    if not r: return
    try:
        root=ET.fromstring(r.content)
        locs=[(x.text or "").strip() for x in root.iter() if x.tag.lower().endswith("loc")]
    except Exception: return
    for loc in locs:
        if not loc: continue
        if loc.lower().split("?")[0].endswith(".xml") or "sitemap" in loc.lower():
            collect_sitemap(loc,seen,found,depth+1)
        else:
            a=canonical_artist_url(loc)
            if a: found.add(a)

def crawl_site():
    found=set(); seen_maps=set()
    for path in SITEMAPS: collect_sitemap(urljoin(BASE,path),seen_maps,found)
    # Sitemap is sometimes partial on Joomla sites; supplement it with public navigation crawling.
    if len(found)<120:
        queue=[(BASE+"/",0)]; seen=set()
        max_pages=int(os.getenv("FACEBOOK_CRAWL_MAX_PAGES","350"))
        while queue and len(seen)<max_pages:
            url,depth=queue.pop(0)
            if url in seen or depth>3: continue
            seen.add(url); r=get(url)
            if not r: continue
            soup=BeautifulSoup(r.text,"html.parser")
            for a in soup.select("a[href]"):
                href=urljoin(url,a.get("href",""))
                artist=canonical_artist_url(href)
                if artist: found.add(artist)
                p=urlparse(href)
                if p.netloc.lower().replace("www.","")=="nachtfragment.de" and depth<3:
                    clean=urlunparse((p.scheme or "https",p.netloc,p.path,p.params,p.query,""))
                    if clean not in seen and not any(x[0]==clean for x in queue) and not any(z in clean.lower() for z in ("/user/","/login","/component/","format=feed")):
                        queue.append((clean,depth+1))
            time.sleep(0.12)
    print("Website-Crawl:",len(found),"Artist-URLs gefunden")
    return found

def clean_facebook(raw):
    try:
        u=urlparse(urljoin(BASE,raw)); host=u.netloc.lower().split(":")[0]
        if not (host=="facebook.com" or host.endswith(".facebook.com") or host=="fb.com" or host.endswith(".fb.com")): return ""
        path=re.sub(r"/+","/",u.path or "/").rstrip("/"); low=path.lower()
        if not path or low in ("/","/profile.php") or any(low.startswith(x) for x in BAD): return ""
        query=[(k,v) for k,v in parse_qsl(u.query,keep_blank_values=True) if k=="id"]
        return urlunparse(("https","www.facebook.com",path,"",urlencode(query),""))
    except Exception: return ""

def page_data(url):
    r=get(url)
    if not r: return "",[]
    soup=BeautifulSoup(r.text,"html.parser")
    h=soup.select_one("h1"); title=h.get_text(" ",strip=True) if h else ""
    if not title:
        og=soup.find("meta",property="og:title"); title=og.get("content","").strip() if og else ""
    if not title and soup.title: title=soup.title.get_text(" ",strip=True)
    title=re.sub(r"\s*[|–-]\s*Nachtfragment.*$","",title,flags=re.I).strip()
    raw=[a.get("href","") for a in soup.select("a[href]")]
    raw += re.findall(r"""https?://(?:www\.)?(?:m\.)?(?:facebook\.com|fb\.com)/[^\s"'<>]+""",r.text,re.I)
    links=[]
    for x in raw:
        u=clean_facebook(x.replace("&amp;","&"))
        if u and u not in links: links.append(u)
    return title,links

def public_search(name):
    try:
        r=S.get("https://html.duckduckgo.com/html/",params={"q":f'site:facebook.com "{name}" (band OR music OR official)'},timeout=18)
        r.raise_for_status(); soup=BeautifulSoup(r.text,"html.parser"); out=[]
        norm=lambda s: re.sub(r"[^a-z0-9]+","",s.lower()); target=norm(name)
        for item in soup.select(".result"):
            a=item.select_one(".result__a")
            if not a: continue
            href=a.get("href","")
            if "uddg=" in href: href=parse_qs(urlparse(href).query).get("uddg",[href])[0]
            u=clean_facebook(href)
            if not u or any(x["url"]==u for x in out): continue
            title=(item.select_one(".result__title") or a).get_text(" ",strip=True)
            sn=item.select_one(".result__snippet"); snippet=sn.get_text(" ",strip=True) if sn else ""
            text=title+" "+snippet; n=norm(text)
            score=(3 if target and target in n else 0)+(1 if any(w in text.lower() for w in ("official","band","music","artist")) else 0)
            if re.search(r"/(posts|photos|videos|groups|events)/",u,re.I): score-=2
            out.append({"url":u,"title":title[:220],"snippet":snippet[:350],"score":score,"source":"public_search"})
        return sorted(out,key=lambda x:x["score"],reverse=True)[:5]
    except Exception as e:
        print("Öffentliche Suche fehlgeschlagen:",name,str(e)[:160]); return []

def valid_artist_url(url):
    return bool(re.search(r"^https://nachtfragment\.de/index\.php/artists/[^/?#]+$",url))

def main():
    old_artists={}; old_fb={}
    for path,target in ((ROOT/"data/artists.json",old_artists),(ROOT/"data/facebook-artists.json",old_fb)):
        if path.exists():
            try:
                for a in json.loads(path.read_text(encoding="utf-8")).get("artists",[]): target[a.get("nachtfragment_url","")]=a
            except Exception: pass
    urls=crawl_site()
    # Keep the known catalogue if the website temporarily blocks the crawler.
    urls.update(u for u in old_artists if valid_artist_url(u))
    urls.update(u for u in old_fb if valid_artist_url(u))
    entries=[]
    for url in sorted(urls):
        previous=old_artists.get(url,{})
        title,_=page_data(url); slug=unquote(url.rstrip("/").rsplit("/",1)[-1])
        name=title or previous.get("name") or re.sub(r"[-_]+"," ",slug).title()
        if not name or any(x in name.lower() for x in SKIP): continue
        entries.append({"name":name,"nachtfragment_url":url})
        time.sleep(0.15)
    artists=sorted({a["nachtfragment_url"]:a for a in entries}.values(),key=lambda x:x["name"].casefold())
    (ROOT/"data/artists.json").write_text(json.dumps({
        "updated_at":datetime.now(timezone.utc).isoformat(),"source":"Live crawl of Nachtfragment public sitemap and artist pages",
        "count":len(artists),"artists":artists},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Artist-Stammliste aktualisiert:",len(artists))
    output=[]; pause=float(os.getenv("FACEBOOK_QUERY_PAUSE","1.0"))
    for i,a in enumerate(artists,1):
        name=a["name"]; url=a["nachtfragment_url"]
        _,links=page_data(url)
        candidates=[{"url":u,"title":"Auf der Nachtfragment-Artistseite verlinkt","snippet":"","score":5,"source":"nachtfragment"} for u in links]
        if not candidates: candidates=public_search(name)
        prev=old_fb.get(url,{})
        output.append({"name":name,"nachtfragment_url":url,"facebook_url":candidates[0]["url"] if candidates else "",
            "match_status":"found_on_artist_page" if links else ("public_search_candidate" if candidates else "not_found"),
            "candidates":candidates,"follow_status":prev.get("follow_status","not_checked"),"notes":prev.get("notes","")})
        print(f"[{i}/{len(artists)}] {name}: {len(candidates)} Facebook-Kandidaten")
        time.sleep(pause)
    result={"updated_at":datetime.now(timezone.utc).isoformat(),
        "source":"Live Nachtfragment artist crawl, official page links and publicly indexed search results",
        "count":len(output),"notice":"Facebook matches are suggestions requiring manual verification. Following is always manual; no Facebook login or automated follow actions.",
        "artists":output}
    out=ROOT/"data/facebook-artists.json"; out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Fertig:",len(output),"Artists;",sum(bool(x["facebook_url"]) for x in output),"mit Facebook-Kandidat")

if __name__=="__main__": main()
