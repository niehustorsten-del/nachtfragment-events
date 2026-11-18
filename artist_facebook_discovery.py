from __future__ import annotations
import json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, parse_qs
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent
UA="Mozilla/5.0 (compatible; NachtfragmentFacebookFinder/1.0; +https://nachtfragment.de)"
S=requests.Session(); S.headers.update({"User-Agent":UA,"Accept-Language":"de,en;q=0.8"})
BAD=("/watch","/reel","/share","/login","/help","/policies","/events","/groups","/marketplace","/gaming","/search")
SKIP=("newcomer","weblinks","linkliste","rezension","top 50","playlist")

def clean(raw):
    try:
        u=urlparse(raw); host=u.netloc.lower().split(":")[0]
        if not (host=="facebook.com" or host.endswith(".facebook.com") or host=="fb.com" or host.endswith(".fb.com")): return ""
        path=re.sub(r"/+","/",u.path or "/").rstrip("/"); low=path.lower()
        if not path or low=="/" or low=="/profile.php" or any(low.startswith(x) for x in BAD): return ""
        query=[(k,v) for k,v in parse_qsl(u.query,keep_blank_values=True) if k=="id"]
        return urlunparse(("https","www.facebook.com",path,"",urlencode(query),""))
    except Exception: return ""

def artist_page(item):
    name=str(item.get("name","")).strip(); url=str(item.get("nachtfragment_url",""))
    return bool(name and not any(x in name.lower() for x in SKIP) and re.search(r"/index\.php/artists/[^/?#]+$",url))

def page_links(url):
    try:
        r=S.get(url,timeout=18); r.raise_for_status(); soup=BeautifulSoup(r.text,"html.parser"); out=[]
        raw=[a.get("href","") for a in soup.select("a[href]")]
        raw += re.findall(r"https?://(?:www\\.)?(?:m\\.)?facebook\\.com/[^\\s\"'<>]+",r.text,re.I)
        for x in raw:
            u=clean(x.replace("&amp;","&"))
            if u and u not in out: out.append(u)
        return out
    except Exception as e:
        print("Artistseite nicht erreichbar:",url,e); return []

def public_search(name):
    try:
        r=S.get("https://html.duckduckgo.com/html/",params={"q":f'site:facebook.com "{name}" music band artist'},timeout=18)
        r.raise_for_status(); soup=BeautifulSoup(r.text,"html.parser"); out=[]
        for item in soup.select(".result"):
            a=item.select_one(".result__a")
            if not a: continue
            href=a.get("href","")
            if "uddg=" in href: href=parse_qs(urlparse(href).query).get("uddg",[href])[0]
            u=clean(href)
            if not u or any(x["url"]==u for x in out): continue
            title=(item.select_one(".result__title") or a).get_text(" ",strip=True)
            sn=item.select_one(".result__snippet"); snippet=sn.get_text(" ",strip=True) if sn else ""
            norm=lambda s: re.sub(r"[^a-z0-9]+","",s.lower())
            score=(2 if norm(name) and norm(name) in norm(title+" "+snippet) else 0)+(1 if any(w in (title+" "+snippet).lower() for w in ("official","band","music","artist")) else 0)
            out.append({"url":u,"title":title[:220],"snippet":snippet[:350],"score":score,"source":"public_search"})
        return out[:5]
    except Exception as e:
        print("Öffentliche Suche fehlgeschlagen:",name,e); return []

def main():
    src=json.loads((ROOT/"data/artists.json").read_text(encoding="utf-8"))
    artists=sorted((x for x in src.get("artists",[]) if artist_page(x)),key=lambda x:x["name"].casefold())
    limit=int(os.getenv("FACEBOOK_MAX_ARTISTS","0"))
    if limit: artists=artists[:limit]
    output_file=ROOT/"data/facebook-artists.json"; old={}
    if output_file.exists():
        try: old={x.get("name"):x for x in json.loads(output_file.read_text(encoding="utf-8")).get("artists",[])}
        except Exception: pass
    output=[]
    for i,a in enumerate(artists,1):
        name=a["name"].strip(); links=page_links(a["nachtfragment_url"])
        candidates=[{"url":u,"title":"Auf der Nachtfragment-Artistseite verlinkt","snippet":"","score":5,"source":"nachtfragment"} for u in links]
        if not candidates: candidates=public_search(name)
        prev=old.get(name,{})
        output.append({"name":name,"nachtfragment_url":a["nachtfragment_url"],"facebook_url":candidates[0]["url"] if candidates else "",
          "match_status":"found_on_artist_page" if links else ("public_search_candidate" if candidates else "not_found"),
          "candidates":candidates,"follow_status":prev.get("follow_status","not_checked"),"notes":prev.get("notes","")})
        print(f"[{i}/{len(artists)}] {name}: {len(candidates)} Treffer")
        time.sleep(float(os.getenv("FACEBOOK_QUERY_PAUSE","1.4")))
    result={"updated_at":datetime.now(timezone.utc).isoformat(),"source":"Public Nachtfragment artist pages and publicly indexed search results",
      "count":len(output),"notice":"Matches require manual verification. No login, private content access, or automated Facebook follow actions.","artists":output}
    output_file.parent.mkdir(parents=True,exist_ok=True); output_file.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Fertig:",len(output),"Artists;",sum(bool(x["facebook_url"]) for x in output),"mit Facebook-Kandidat")
if __name__=="__main__": main()
