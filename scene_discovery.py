#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent; DATA=ROOT/'data'
DB=DATA/'nachtfragment.json'; CAND=DATA/'scene_candidates.json'; CHANGES=DATA/'scene_changes.json'; CACHE=DATA/'geocache.json'; QUERIES=ROOT/'scene_search_queries.json'
KEY=os.getenv('SERPAPI_KEY','').strip(); UA='Nachtfragment-SceneDiscovery/4.0'; TIMEOUT=15
PERMANENT={'club','bar','shop','store','venue','organizer','organization','organisation','location'}
EVENT_WORDS=['festival','festivals','festivalhopper','event','events','eventim','veranstaltung','veranstaltungen','termine','tickets','ticket','tour','concert','concerts','konzert','konzerte','gig','gigs','party','parties','wgt','mera luna','lineup','line-up','calendar','programme','program','agenda','upcoming']
BLOCKED=['festivalhopper.de','eventbrite.','eventim.','ticketmaster.','bandsintown.','songkick.','wikipedia.org','tripadvisor.','yelp.','foursquare.','ra.co']
SCENE={'Gothic Core':['gothic','goth','goth night','gothic night'],'Darkwave / Wave':['darkwave','dark wave','coldwave','cold wave','wave night'],'EBM / Industrial':['ebm','electronic body music','industrial','industrial night'],'Dark Electro / Futurepop':['dark electro','futurepop','aggrotech','cyber goth','cybergoth'],'Post-Punk / Deathrock':['post-punk','post punk','deathrock','dark punk'],'Alternative / Dark Rock':['dark rock','dark alternative']}
VENUE=['goth night','gothic night','darkwave','dark wave','ebm','industrial night','dark electro','futurepop','deathrock','post-punk','cybergoth','goth club','goth bar','dark club']
SHOP=['gothic','goth','dark fashion','darkwear','alternative fashion','alternative clothing','punk','industrial','deathrock','cyber goth']
CITIES={'Berlin':'Germany','Hamburg':'Germany','Munich':'Germany','München':'Germany','Cologne':'Germany','Köln':'Germany','Frankfurt':'Germany','Leipzig':'Germany','Dresden':'Germany','Stuttgart':'Germany','Hannover':'Germany','Vienna':'Austria','Wien':'Austria','Graz':'Austria','Zurich':'Switzerland','Zürich':'Switzerland','Basel':'Switzerland','Paris':'France','London':'United Kingdom','Manchester':'United Kingdom','Amsterdam':'Netherlands','Brussels':'Belgium','Copenhagen':'Denmark','Stockholm':'Sweden','Oslo':'Norway','Warsaw':'Poland','Prague':'Czech Republic','Budapest':'Hungary','Madrid':'Spain','Barcelona':'Spain','Milan':'Italy','Rome':'Italy','Istanbul':'Turkey','New York':'United States','Los Angeles':'United States','Chicago':'United States','Seattle':'United States','Portland':'United States','San Francisco':'United States','Toronto':'Canada','Montreal':'Canada','Sydney':'Australia','Melbourne':'Australia','Brisbane':'Australia','Adelaide':'Australia','Perth':'Australia','Auckland':'New Zealand','Tokyo':'Japan','Osaka':'Japan','Seoul':'South Korea'}
ALIASES={'de':'Germany','germany':'Germany','deutschland':'Germany','at':'Austria','austria':'Austria','österreich':'Austria','ch':'Switzerland','switzerland':'Switzerland','schweiz':'Switzerland','fr':'France','france':'France','it':'Italy','italy':'Italy','es':'Spain','spain':'Spain','uk':'United Kingdom','united kingdom':'United Kingdom','us':'United States','usa':'United States','united states':'United States','ca':'Canada','canada':'Canada','au':'Australia','australia':'Australia','nz':'New Zealand','new zealand':'New Zealand'}
COUNTRY_NAMES={'Germany':'Deutschland','Austria':'Österreich','Switzerland':'Schweiz','France':'Frankreich','Italy':'Italien','Spain':'Spanien','United Kingdom':'Vereinigtes Königreich','United States':'USA','Canada':'Kanada','Australia':'Australien','New Zealand':'Neuseeland','Japan':'Japan','South Korea':'Südkorea','Turkey':'Türkei'}

def load(p,d):
    try:return json.loads(p.read_text(encoding='utf-8')) if p.exists() else d
    except:return d

def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def norm(u):
    try:
        p=urlparse(u)
        return urlunparse((p.scheme,p.netloc.lower().split(':')[0],p.path.rstrip('/') or '/','','','')) if p.scheme in ('http','https') and p.netloc else ''
    except:return ''
def blocked(text,title='',url=''):
    h=' '.join([text or '',title or '',url or '']).lower()
    if any(x in h for x in BLOCKED):return True
    return any(re.search(r'(?<!\w)'+re.escape(w)+r'(?!\w)',h) for w in EVENT_WORDS)
def fetch(u):
    try:
        with urlopen(Request(u,headers={'User-Agent':UA}),timeout=TIMEOUT) as r:return r.read().decode('utf-8','ignore')[:180000]
    except:return ''
def serp(q):
    u='https://serpapi.com/search.json?engine=google&q='+quote(q)+'&num=10&api_key='+quote(KEY)
    with urlopen(Request(u,headers={'User-Agent':UA}),timeout=TIMEOUT) as r:return json.loads(r.read().decode())
def textclean(s):return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',s or '')).strip()
def cats(t):
    l=t.lower();return [k for k,v in SCENE.items() if any(x in l for x in v)]
def kind(t):
    l=t.lower()
    if any(x in l for x in SHOP) and any(x in l for x in ['shop','store','clothing','fashion','products','cart','collections','boutique']):return 'shop'
    if any(x in l for x in ['promoter','promoters','promotions','veranstalter','event organizer','event organiser','collective']):return 'organizer'
    if any(x in l for x in ['club','nightclub','night club','discotheque','venue']) and any(x in l for x in VENUE):return 'club'
    if any(x in l for x in ['goth bar','dark bar','alternative bar','bar','pub','lounge']) and any(x in l for x in VENUE):return 'bar'
    return ''
def location(t,hint):
    h=ALIASES.get(hint.lower(),hint) if hint else ''
    for city,country in sorted(CITIES.items(),key=lambda x:-len(x[0])):
        if re.search(r'(?<!\w)'+re.escape(city)+r'(?!\w)',t,re.I) and (not h or h.lower()==country.lower()):return city,country
    return '',h
def address(t):
    for p in [r'(?:address|adresse|location|standort|find us|visit us)\s*[:\-]\s*([^.;|]{10,180})',r'\b\d{1,5}\s+[A-Za-zÄÖÜäöüß0-9.\' -]{3,70}(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Boulevard|Blvd|Way|Strasse|Straße|Gasse|Weg)\b[^.;|]{0,80}']:
        m=re.search(p,t,re.I)
        if m:return re.sub(r'\s+',' ',m.group(1) if m.lastindex else m.group(0)).strip(' ,.-')
    return ''
def online_only(t):
    l=t.lower();return any(x in l for x in ['online shop','online store','shop online','worldwide shipping']) and not any(x in l for x in ['store locations','our stores','find a store','shop address','visit us'])
def dkey(n,c,co):return (re.sub(r'\W+','',str(n).lower()),re.sub(r'\W+','',str(c).lower()),str(co).lower())
def is_scene(x):
    if not isinstance(x,dict):return False
    ts=x.get('type',[]);ts=[ts] if isinstance(ts,str) else ts;ts={str(a).lower() for a in ts}
    if str(x.get('record_type','')).lower()=='event' or ts&{'event','festival'}:return False
    return bool(ts&PERMANENT) and not blocked(' '.join([str(x.get('name','')),str(x.get('url','')),str(x.get('description','')),str(x.get('discovery_query',''))]),str(x.get('name','')),str(x.get('url','')))
def clean_candidates(xs):
    out=[];seen=set()
    for x in xs:
        if not is_scene(x):continue
        k=(norm(str(x.get('url',''))),dkey(x.get('name',''),x.get('city',''),x.get('country','')))
        if k not in seen:seen.add(k);out.append(x)
    return out
def gid(n,c,co):return re.sub(r'[^a-z0-9]+','-',f'{n}-{c}-{co}'.lower()).strip('-')[:90]
def geocode(addr,city,country,cache):
    if not addr:return None
    q=', '.join(x for x in [addr,city,country] if x);k=q.lower()
    if k in cache:return cache[k]
    try:
        u='https://nominatim.openstreetmap.org/search?format=json&limit=1&q='+quote(q)
        with urlopen(Request(u,headers={'User-Agent':UA}),timeout=TIMEOUT) as r:a=json.loads(r.read().decode())
        if a:
            v={'lat':float(a[0]['lat']),'lng':float(a[0]['lon'])};cache[k]=v;time.sleep(1);return v
    except:return None

def main():
    if not KEY:raise SystemExit('SERPAPI_KEY fehlt')
    DATA.mkdir(exist_ok=True);db=load(DB,[]);cand=clean_candidates(load(CAND,[]));changes=load(CHANGES,[]);cache=load(CACHE,{})
    cfg=load(QUERIES,{'batches':[]});batches=cfg.get('batches',[])
    if not batches:save(CAND,cand);save(CHANGES,changes);save(CACHE,cache);return
    qs=batches[(datetime.now(timezone.utc).timetuple().tm_yday-1)%len(batches)]
    existing={dkey(x.get('name',''),x.get('city',''),x.get('country','')) for x in db if isinstance(x,dict)};urls={norm(str(x.get('url',''))) for x in db if isinstance(x,dict)}
    ck={dkey(x.get('name',''),x.get('city',''),x.get('country','')) for x in cand};cu={norm(str(x.get('url',''))) for x in cand}
    for qd in qs:
        q=qd['query'];hint=qd.get('country','')
        try:data=serp(q)
        except Exception as e:print(e);continue
        for r in data.get('organic_results',[])[:10]:
            title=str(r.get('title','')).strip();u=norm(str(r.get('link','')));snippet=str(r.get('snippet',''))
            if not title or not u or blocked(snippet,title,u):continue
            page=textclean(fetch(u));t=f'{title} {snippet} {page}'
            if blocked(t,title,u):continue
            cs=cats(t);knd=kind(t)
            if not cs or knd not in PERMANENT:continue
            city,country=location(t,hint);addr=address(t);physical=not(knd=='shop' and online_only(t))
            score=min(40,len(cs)*10)+(15 if city else 0)+(15 if addr else 0)+(20 if knd in ('club','bar') else 10)
            publish=score>=70 and (knd=='shop' or bool(city)) and (not physical or bool(addr))
            coords=geocode(addr,city,country,cache) if publish and physical else None
            if publish and physical and not coords:publish=False
            rec={'id':gid(title,city,country),'name':title,'city':city,'country':country,'country_name':COUNTRY_NAMES.get(country,country),'type':[knd]+(['venue'] if knd in ('club','bar','organizer') else []),'categories':cs,'url':u,'description':f'Automatisch entdeckter permanenter {knd} für die Nachtfragment-Szene.','verified':publish,'audit_status':'green' if publish else 'yellow','source':'SerpApi Scene Discovery V4','discovery_query':q,'scene_score':score,'is_physical':physical,'map_visible':bool(coords)}
            if addr:rec['address']=addr
            if coords:rec.update(coords)
            if not is_scene(rec):continue
            key=dkey(rec['name'],rec['city'],rec['country'])
            if key in existing or key in ck or u in urls or u in cu:continue
            if publish:db.append(rec);existing.add(key);urls.add(u);changes.append({'timestamp':datetime.now(timezone.utc).isoformat(),'action':'scene_discovery_add','id':rec['id']})
            else:cand.append(rec);ck.add(key);cu.add(u)
    save(DB,db);save(CAND,clean_candidates(cand));save(CHANGES,changes[-2000:]);save(CACHE,cache)
if __name__=='__main__':main()
