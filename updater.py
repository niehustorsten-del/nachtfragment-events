#!/usr/bin/env python3
"""Nachtfragment automatic discovery updater v3.

Stdlib only. It discovers scene-relevant events/festivals from a curated source
registry, supports HTML/RSS/Atom/ICS, extracts dates and locations, classifies
scene relevance, creates Google Maps links, optionally geocodes with Nominatim,
and keeps uncertain discoveries in candidates.json instead of publishing them.
"""
import json, re, hashlib, html, os, time, urllib.parse
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

ROOT=os.path.dirname(os.path.abspath(__file__))
DATA=os.path.join(ROOT,'data','nachtfragment.json')
CANDIDATES=os.path.join(ROOT,'data','candidates.json')
CHANGES=os.path.join(ROOT,'data','changes.json')
GEOCACHE=os.path.join(ROOT,'data','geocache.json')
SOURCES=os.path.join(ROOT,'discovery_sources.json')
SEARCH_QUERIES=os.path.join(ROOT,'search_queries.json')
SERPAPI_KEY=os.environ.get('SERPAPI_KEY','').strip()
UA='Nachtfragment-Updater/4.0 (+https://nachtfragment.de)'
NOW=datetime.now(timezone.utc)
TODAY=NOW.date().isoformat()

DATE_PATTERNS=[
 re.compile(r'\b(?:0?[1-9]|[12]\d|3[01])[./-](?:0?[1-9]|1[0-2])[./-](?:20\d{2})\b'),
 re.compile(r'\b20\d{2}[./-](?:0?[1-9]|1[0-2])[./-](?:0?[1-9]|[12]\d|3[01])\b'),
 re.compile(r'\b(?:0?[1-9]|[12]\d|3[01])\.?\s*(?:Jan|Feb|Mär|Mar|Apr|Mai|May|Jun|Jul|Aug|Sep|Okt|Oct|Nov|Dez|Dec)[a-zäöü]*\.?\s*20\d{2}\b', re.I)
]
SCENE={
 'gothic_core':['gothic','goth','batcave','goth club','gothic rock'],
 'darkwave_wave':['darkwave','dark wave','wave','coldwave','minimal wave','ethereal wave'],
 'ebm_industrial':['ebm','industrial','aggrotech','electro-industrial'],
 'dark_electro_futurepop':['dark electro','futurepop','electropop','dark electronic','synthpop'],
 'postpunk_deathrock':['post-punk','postpunk','deathrock','death rock'],
 'alternative_darkrock':['dark rock','alternative rock','alternative']
}
LABELS={'gothic_core':'🖤 Gothic Core','darkwave_wave':'🌑 Darkwave / Wave','ebm_industrial':'⚡ EBM / Industrial','dark_electro_futurepop':'🧪 Dark Electro / Futurepop','postpunk_deathrock':'🕷️ Post-Punk / Deathrock','alternative_darkrock':'🎸 Alternative / Dark Rock'}
COUNTRIES={'DE':'Deutschland','PL':'Polen','MT':'Malta','AT':'Österreich','CH':'Schweiz','NL':'Niederlande','BE':'Belgien','FR':'Frankreich','GB':'Vereinigtes Königreich','US':'USA','AU':'Australien','EU':'Europa'}
CITY_HINTS=re.compile(r'\b(Hamburg|Berlin|Leipzig|Köln|Cologne|Oberhausen|Chemnitz|Hildesheim|Dresden|München|Munich|Stuttgart|Essen|Erfurt|Jena|Bolków|Malta|Valletta|London|Paris|Amsterdam|Brussels|Warsaw|Warschau|Melbourne|Adelaide|Sydney|Auckland|New York|Los Angeles)\b',re.I)

class LinkParser(HTMLParser):
 def __init__(self,base):
  super().__init__(); self.base=base; self.items=[]; self.href=None; self.current=[]
 def handle_starttag(self,tag,attrs):
  if tag.lower()=='a':
   d=dict(attrs); self.href=urllib.parse.urljoin(self.base,d.get('href','')); self.current=[]
 def handle_data(self,data):
  if self.href: self.current.append(data)
 def handle_endtag(self,tag):
  if tag.lower()=='a' and self.href:
   text=re.sub(r'\s+',' ',html.unescape(''.join(self.current))).strip()
   if text: self.items.append((text,self.href))
   self.href=None; self.current=[]

def fetch(url,accept='*/*'):
 req=Request(url,headers={'User-Agent':UA,'Accept':accept})
 with urlopen(req,timeout=30) as r:
  raw=r.read()
  ctype=r.headers.get_content_type()
  return r.status,ctype,raw.decode('utf-8','ignore')

def slug(name,city=''):
 return hashlib.sha1((name+'|'+city).lower().encode('utf-8')).hexdigest()[:14]

def date_text(text):
 for p in DATE_PATTERNS:
  m=p.search(text)
  if m: return m.group(0)
 return None

def scene_tags(text):
 t=text.lower(); tags=[]
 for k,words in SCENE.items():
  if any(w in t for w in words): tags.append(k)
 return tags

def labels(tags): return [LABELS[x] for x in tags]

def maps_url(name,city='',country=''):
 q=', '.join(x for x in [name,city,country] if x)
 return 'https://www.google.com/maps/search/?api=1&query='+urllib.parse.quote_plus(q)

def geocode(name, city, country, geocache):
    if not city and not country: return None
    q=', '.join(x for x in [name, city, country] if x)
    key=q.lower()
    if key in geocache: return geocache[key]
    url='https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q='+urllib.parse.quote_plus(q)
    try:
        req=Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
        with urlopen(req,timeout=20) as r:
            arr=json.loads(r.read().decode('utf-8','ignore'))
        if arr:
            hit={'lat':float(arr[0]['lat']),'lng':float(arr[0]['lon'])}
            geocache[key]=hit
            time.sleep(1.05)  # public Nominatim rate-limit courtesy
            return hit
    except Exception as e:
        print('GEOCODE ERROR',q,repr(e))
    geocache[key]=None
    return None

def maps_dir(lat=None,lng=None,name='',city='',country=''):
 if isinstance(lat,(int,float)) and isinstance(lng,(int,float)):
  q=f'{lat},{lng}'
 else: q=', '.join(x for x in [name,city,country] if x)
 return 'https://www.google.com/maps/dir/?api=1&destination='+urllib.parse.quote_plus(q)

def extract_city(text, source):
 m=CITY_HINTS.search(text)
 if m: return m.group(1)
 # common source-local hints
 hints=source.get('city_hints',[])
 for c in hints:
  if c.lower() in text.lower(): return c
 return None

def parse_html(source,body):
 p=LinkParser(source['url']); p.feed(body); out=[]
 for title,url in p.items:
  blob=title+' '+url
  if not scene_tags(blob) and 'festival' not in blob.lower(): continue
  d=date_text(blob)
  if not d: continue
  if len(title)<4 or title.lower() in {'mehr','details','tickets','website','info'}: continue
  out.append({'name':html.unescape(title).strip(),'url':url,'date_text':d,'raw':blob})
 return out

def strip_ns(tag): return tag.split('}',1)[-1].lower()
def parse_feed(source,body):
 try: root=ET.fromstring(body)
 except ET.ParseError: return []
 out=[]
 for node in root.iter():
  if strip_ns(node.tag) not in ('item','entry','vevent'): continue
  vals={strip_ns(c.tag):re.sub(r'\s+',' ',''.join(c.itertext())).strip() for c in node}
  title=vals.get('title') or vals.get('summary') or vals.get('name')
  url=vals.get('link') or source['url']
  if not title: continue
  blob=' '.join(vals.values())
  d=date_text(blob) or vals.get('dtstart')
  if not d: continue
  if not scene_tags(blob) and 'festival' not in blob.lower(): continue
  out.append({'name':html.unescape(title),'url':urllib.parse.urljoin(source['url'],url),'date_text':d,'raw':blob,'city':extract_city(blob,source)})
 return out

def parse_ics(source,body):
 lines=re.sub(r'\r?\n[ \t]','',body).splitlines(); out=[]; ev={}; inside=False
 def flush():
  if not ev: return
  title=ev.get('SUMMARY') or ev.get('NAME'); blob=' '.join(ev.values())
  d=ev.get('DTSTART') or date_text(blob)
  if title and d and (scene_tags(blob) or 'festival' in blob.lower()):
   out.append({'name':title,'url':ev.get('URL',source['url']),'date_text':d,'raw':blob,'city':extract_city(blob,source)})
 for line in lines:
  if line=='BEGIN:VEVENT': inside=True; ev={}; continue
  if line=='END:VEVENT': flush(); inside=False; ev={}; continue
  if inside and ':' in line:
   k,v=line.split(':',1); ev[k.split(';',1)[0].upper()]=v.strip()
 return out

def discover(source):
 status,ctype,body=fetch(source['url'],'text/html,application/xhtml+xml,application/xml,text/xml,text/calendar;q=0.9,*/*;q=0.5')
 kind=source.get('kind','html_calendar')
 if kind in ('rss','atom','feed'): items=parse_feed(source,body)
 elif kind=='ics': items=parse_ics(source,body)
 else: items=parse_html(source,body)
 return status,ctype,items

def score_candidate(c,source):
 score=0; reasons=[]
 if source.get('priority')=='high': score+=3; reasons.append('hoch priorisierte Quelle')
 elif source.get('priority')=='medium': score+=2
 if source.get('kind')=='official': score+=3; reasons.append('offizielle Quelle')
 elif source.get('kind') in ('ics','rss','atom','feed'): score+=2
 if c.get('date_text'): score+=2; reasons.append('Datum erkannt')
 tags=scene_tags(c.get('raw','')+' '+c.get('name',''))
 if tags: score+=len(tags); reasons.append('Szene-Keywords erkannt')
 if c.get('city'): score+=1; reasons.append('Ort erkannt')
 if 'festival' in (c.get('name','')+' '+c.get('raw','')).lower(): score+=2; reasons.append('Festival erkannt')
 return score,tags,reasons



def serpapi_search(query, gl='de', hl='en'):
    """Search the wider web through SerpApi when SERPAPI_KEY is configured."""
    if not SERPAPI_KEY:
        return []
    params=urllib.parse.urlencode({
        'engine':'google', 'q':query, 'gl':gl, 'hl':hl,
        'num':10, 'api_key':SERPAPI_KEY, 'safe':'active'
    })
    url='https://serpapi.com/search?'+params
    try:
        status,ctype,body=fetch(url,'application/json')
        obj=json.loads(body)
        return obj.get('organic_results',[]) or []
    except Exception as e:
        print('SEARCH ERROR',query,repr(e))
        return []

def parse_search_result(result, query):
    title=html.unescape(str(result.get('title') or '')).strip()
    link=str(result.get('link') or '').strip()
    snippet=html.unescape(str(result.get('snippet') or '')).strip()
    blob=' '.join(x for x in [title,snippet,result.get('source',''),result.get('displayed_link','')] if x)
    if not link or not title: return None
    # Search results are leads, not proof. Require a scene keyword and a date-like signal.
    if not scene_tags(blob) and 'festival' not in blob.lower() and 'goth' not in blob.lower(): return None
    d=date_text(blob)
    if not d:
        # Search result date fields occasionally carry the event date.
        d=date_text(str(result.get('date') or ''))
    if not d: return None
    return {
        'name':title,
        'url':link,
        'date_text':d,
        'raw':blob,
        'city':extract_city(blob,{}),
        'search_query':query,
        'search_snippet':snippet
    }

def discover_web_search():
    """Broad discovery pass. Results are deliberately treated as candidates until page verification."""
    if not SERPAPI_KEY:
        print('WEB SEARCH: skipped (SERPAPI_KEY not configured)')
        return []
    queries=load_json(SEARCH_QUERIES,{}).get('queries',[])
    out=[]; seen=set()
    for q in queries:
        query=q.get('q','').strip()
        if not query: continue
        results=serpapi_search(query,q.get('gl','de'),q.get('hl','en'))
        print('WEB SEARCH',query,'results',len(results))
        for r in results:
            c=parse_search_result(r,query)
            if not c: continue
            key=c['url'].split('#',1)[0]
            if key in seen: continue
            seen.add(key); out.append(c)
    return out

def load_json(path,default):
 try:
  with open(path,encoding='utf-8') as f: return json.load(f)
 except Exception: return default

def save_json(path,obj):
 with open(path,'w',encoding='utf-8') as f: json.dump(obj,f,ensure_ascii=False,indent=2)

def main():
 data=load_json(DATA,[]); candidates=load_json(CANDIDATES,[]); changes=load_json(CHANGES,[]); geocache=load_json(GEOCACHE,{})
 if not isinstance(data,list): raise SystemExit('data/nachtfragment.json muss ein Array sein')
 if not isinstance(candidates,list): candidates=[]
 known={(x.get('name','').strip().lower(),x.get('city','').strip().lower(),x.get('country','').strip().lower()) for x in data}
 cand_known={(x.get('name','').strip().lower(),x.get('city','').strip().lower(),x.get('country','').strip().lower()) for x in candidates}
 new_pub=0; new_cand=0
 for source in load_json(SOURCES,[]):
  try:
   status,ctype,items=discover(source); print(source['name'],status,ctype,'found',len(items))
   for c in items:
    city=c.get('city') or ''
    country=COUNTRIES.get(source.get('country'),source.get('country',''))
    key=(c['name'].strip().lower(),city.lower(),country.lower())
    score,tags,reasons=score_candidate(c,source)
    geo=geocode(c['name'],city,country,geocache) if city else None
    rec={
     'id':'auto-'+slug(c['name'],city), 'record_type':'event', 'name':c['name'],
     'city':city or None, 'country':source.get('country'), 'country_name':country,
     'type':['event','festival'] if ('festival' in (c['name']+' '+c.get('raw','')).lower() or source.get('kind')=='official' and 'festival' in ' '.join(source.get('keywords',[])).lower()) else ['event'],
     'categories':labels(tags), 'szenerelevanz':tags, 'szenerelevanz_labels':labels(tags),
     'url':c['url'], 'source_url':source['url'], 'date_text':c['date_text'],
     'verified':False, 'aktivitaet':'unchecked','aktivitaet_label':'⚪ nicht ausreichend geprüft',
     'discovery_status':'candidate','auto_discovered':True,'confidence_score':score,
     'confidence_reasons':reasons,'auto_sources':[source['url']], 'discovered_at':NOW.isoformat(),
     'google_maps_url':maps_url(c['name'],city,country),
     'google_maps_directions_url':maps_dir(lat=geo['lat'],lng=geo['lng'],name=c['name'],city=city,country=country),
     'geocoded':bool(geo),
     'google_maps_status':'search_link'
    }
    if geo:
     rec['lat']=geo['lat']; rec['lng']=geo['lng']
     rec['google_maps_coords_url']='https://www.google.com/maps/search/?api=1&query='+urllib.parse.quote_plus(f"{geo['lat']},{geo['lng']}")
     rec['google_maps_status']='geocoded'
    # Official, strongly evidenced items can be published; all others stay candidates.
    publish = source.get('kind')=='official' and score>=7
    if key in known:
     for x in data:
      if (x.get('name','').strip().lower(),x.get('city','').strip().lower(),x.get('country_name',x.get('country','')).strip().lower())==key:
       x.setdefault('auto_sources',[])
       if source['url'] not in x['auto_sources']: x['auto_sources'].append(source['url'])
       x['last_source_check']=NOW.isoformat(); break
     continue
    if key in cand_known: continue
    if publish:
     rec['discovery_status']='published'; rec['verified']=True; rec['verified_date']=TODAY; rec['aktivitaet']='active'; rec['aktivitaet_label']='🟢 aktuell aktiv'
     data.append(rec); known.add(key); new_pub+=1
     changes.insert(0,{'timestamp':NOW.isoformat(),'type':'published','name':c['name'],'city':city,'source':source['url'],'score':score})
    else:
     candidates.append(rec); cand_known.add(key); new_cand+=1
     changes.insert(0,{'timestamp':NOW.isoformat(),'type':'candidate','name':c['name'],'city':city,'source':source['url'],'score':score})
  except Exception as e:
   print('ERROR',source['name'],repr(e)); changes.insert(0,{'timestamp':NOW.isoformat(),'type':'source_error','source':source.get('url'),'error':str(e)})
 # Broad web-search discovery. Search results are never published solely from the snippet.
 search_items=discover_web_search()
 if search_items:
  search_source={'name':'Web Search Discovery','url':'https://www.google.com/','country':'EU','priority':'medium','kind':'web_search'}
  for c in search_items:
   try:
    # Fetch the actual page before scoring. This turns a search hit into an independently checked lead.
    try:
     st,ct,body=fetch(c['url'],'text/html,application/xhtml+xml,text/calendar,application/xml;q=0.9,*/*;q=0.5')
     page_text=re.sub(r'<[^>]+>',' ',body)
     page_text=html.unescape(re.sub(r'\s+',' ',page_text))[:120000]
    except Exception as e:
     st=0; ct=''; page_text=''; print('PAGE FETCH ERROR',c['url'],repr(e))
    combined=c['raw']+' '+page_text
    tags=scene_tags(combined)
    city=c.get('city') or extract_city(page_text,{}) or ''
    # infer a country from common search-result / page language hints where possible
    country=''
    for code,name in COUNTRIES.items():
     if re.search(r'\b'+re.escape(name)+r'\b',combined,re.I): country=name; break
    if not country:
     country='Europa'
    score=2 if c.get('date_text') else 0
    score+=min(len(tags),4)
    if city: score+=2
    if st==200: score+=2
    if 'festival' in combined.lower(): score+=2
    if any(x in combined.lower() for x in ['tickets','veranstaltung','event','calendar','events']): score+=1
    rec={
      'id':'search-'+slug(c['name'],city), 'record_type':'event', 'name':c['name'],
      'city':city or None, 'country_name':country,
      'type':['event','festival'] if 'festival' in combined.lower() else ['event'],
      'categories':labels(tags), 'szenerelevanz':tags, 'szenerelevanz_labels':labels(tags),
      'url':c['url'], 'source_url':c['url'], 'date_text':c['date_text'],
      'verified':False, 'aktivitaet':'unchecked','aktivitaet_label':'⚪ nicht ausreichend geprüft',
      'discovery_status':'candidate','auto_discovered':True,'search_discovered':True,
      'confidence_score':score,'confidence_reasons':['Websuche gefunden','Originalseite abgerufen' if st==200 else 'Originalseite nicht erreichbar',
      'Datum erkannt']+(['Ort erkannt'] if city else [])+(['Szenebegriffe auf Originalseite gefunden'] if tags else []),
      'auto_sources':[c['url']], 'discovered_at':NOW.isoformat(), 'search_query':c.get('search_query'),
      'search_snippet':c.get('search_snippet',''), 'google_maps_url':maps_url(c['name'],city,country),
      'google_maps_directions_url':maps_dir(name=c['name'],city=city,country=country),
      'google_maps_status':'search_link'
    }
    if city:
     geo=geocode(c['name'],city,country,geocache)
     if geo:
      rec['lat']=geo['lat']; rec['lng']=geo['lng']; rec['geocoded']=True
      rec['google_maps_coords_url']='https://www.google.com/maps/search/?api=1&query='+urllib.parse.quote_plus(f"{geo['lat']},{geo['lng']}")
      rec['google_maps_status']='geocoded'
     else: rec['geocoded']=False
    else: rec['geocoded']=False
    key=(rec['name'].lower(),(rec.get('city') or '').lower(),(rec.get('country_name') or '').lower())
    if key in known or key in cand_known: continue
    # Broad search can publish only when the original page is reachable and evidence is strong.
    publish=(st==200 and score>=10 and bool(tags) and bool(c['date_text']))
    if publish:
     rec['discovery_status']='published'; rec['verified']=True; rec['verified_date']=TODAY; rec['aktivitaet']='active'; rec['aktivitaet_label']='🟢 aktuell aktiv'
     data.append(rec); known.add(key); new_pub+=1
     changes.insert(0,{'timestamp':NOW.isoformat(),'type':'published_web_search','name':c['name'],'city':city,'source':c['url'],'score':score})
    else:
     candidates.append(rec); cand_known.add(key); new_cand+=1
     changes.insert(0,{'timestamp':NOW.isoformat(),'type':'candidate_web_search','name':c['name'],'city':city,'source':c['url'],'score':score})
   except Exception as e:
    print('SEARCH ITEM ERROR',c.get('url'),repr(e))

 # de-duplicate published data and candidates
 def dedupe(rows):
  seen=set(); out=[]
  for x in rows:
   key=(x.get('name','').strip().lower(),str(x.get('city') or '').strip().lower(),str(x.get('country_name',x.get('country','')) or '').strip().lower())
   if key in seen: continue
   seen.add(key); out.append(x)
  return out
 save_json(DATA,dedupe(data)); save_json(CANDIDATES,dedupe(candidates)); save_json(CHANGES,changes[:1000]); save_json(GEOCACHE,geocache)
 print('TOTAL',len(data),'PUBLISHED',new_pub,'CANDIDATES',len(candidates),'NEW_CANDIDATES',new_cand)
if __name__=='__main__': main()
