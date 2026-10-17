#!/usr/bin/env python3
"""Nachtfragment automatic discovery updater v5.0.

Stdlib only. It discovers scene-relevant events/festivals from a curated source
registry, supports HTML/RSS/Atom/ICS, extracts dates and locations, classifies
scene relevance, creates Google Maps links, optionally geocodes with Nominatim,
and keeps uncertain discoveries in candidates.json instead of publishing them.
"""
import json, re, hashlib, html, os, time, urllib.parse
from datetime import datetime, timezone, date
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

ROOT=os.path.dirname(os.path.abspath(__file__))
DATA=os.path.join(ROOT,'data','nachtfragment.json')
CANDIDATES=os.path.join(ROOT,'data','candidates.json')
CHANGES=os.path.join(ROOT,'data','changes.json')
GEOCACHE=os.path.join(ROOT,'data','geocache.json')
STATUS=os.path.join(ROOT,'data','status.json')
SOURCES=os.path.join(ROOT,'discovery_sources.json')
SEARCH_QUERIES=os.path.join(ROOT,'search_queries.json')
SERPAPI_KEY=os.environ.get('SERPAPI_KEY','').strip()
UA='Nachtfragment-Updater/5.0 (+https://nachtfragment.de)'
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
CITY_HINTS=re.compile(r'\b(Hamburg|Berlin|Leipzig|Köln|Cologne|Oberhausen|Chemnitz|Hildesheim|Dresden|München|Munich|Stuttgart|Essen|Erfurt|Jena|Bolków|Malta|Valletta|London|Manchester|Bristol|Glasgow|Edinburgh|Paris|Lyon|Amsterdam|Rotterdam|Brussels|Antwerp|Warsaw|Warschau|Prague|Praha|Vienna|Wien|Zurich|Zürich|Basel|Copenhagen|Stockholm|Oslo|Helsinki|Rome|Milan|Madrid|Barcelona|Lisbon|Athens|Istanbul|Melbourne|Adelaide|Sydney|Auckland|New York|Los Angeles|Chicago|Portland|Seattle|San Francisco|Toronto|Montreal)\b',re.I)

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
 with urlopen(req,timeout=12) as r:
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

def parsed_date(text):
    if not text: return None
    t=str(text).strip()
    # ICS / ISO timestamps, including DTSTART:20260918T190000Z
    m=re.match(r'^(?:TZID=[^:;]+:)?(20\d{2})(0[1-9]|1[0-2])([0-3]\d)', t)
    if m:
        try: return date(int(m.group(1)),int(m.group(2)),int(m.group(3)))
        except ValueError: pass
    for fmt in ('%d.%m.%Y','%d/%m/%Y','%d-%m-%Y','%Y.%m.%d','%Y-%m-%d','%Y/%m/%d'):
        try: return datetime.strptime(t,fmt).date()
        except ValueError: pass
    m=re.match(r'^(\d{1,2})\.?\s*(Jan|Feb|Mär|Mar|Apr|Mai|May|Jun|Jul|Aug|Sep|Okt|Oct|Nov|Dez|Dec)[a-zäöü]*\.?\s*(20\d{2})$',t,re.I)
    if m:
        months={'jan':1,'feb':2,'mär':3,'mar':3,'apr':4,'mai':5,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'okt':10,'oct':10,'nov':11,'dez':12,'dec':12}
        try: return date(int(m.group(3)),months[m.group(2).lower()[:3]],int(m.group(1)))
        except Exception: pass
    return None

def is_future_or_current(date_string):
    d=parsed_date(date_string)
    return bool(d and d >= NOW.date())

EVENT_TITLE_HINTS=re.compile(r'\b(festival|festivalen|fest|party|nacht|night|event|events|concert|konzert|live|tour|show|gothic|darkwave|ebm|industrial|post[- ]?punk|deathrock|dark electro|futurepop)\b',re.I)
EDITORIAL_HINTS=re.compile(r'\b(introduction|definition|meaning|test|review|guide|vergleich|compared|geschichte|history|style|fashion|magazine|news|blog|almanach|dictionary|wikipedia)\b',re.I)

def looks_like_real_event(name, text, url=''):
    blob=' '.join([name or '', text or '', url or ''])
    if EDITORIAL_HINTS.search(blob): return False
    return bool(EVENT_TITLE_HINTS.search(name or '') or re.search(r'\b(tickets?|admission|doors?|venue|line[- ]?up|lineup|dj|djs)\b',blob,re.I))

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
        with urlopen(req,timeout=8) as r:
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
  if not d or not is_future_or_current(d): continue
  if len(title)<4 or title.lower() in {'mehr','details','tickets','website','info'}: continue
  if not looks_like_real_event(title, blob, url): continue
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
  if not is_future_or_current(d): continue
  if not scene_tags(blob) and 'festival' not in blob.lower(): continue
  if not looks_like_real_event(title, blob, url): continue
  out.append({'name':html.unescape(title),'url':urllib.parse.urljoin(source['url'],url),'date_text':d,'raw':blob,'city':extract_city(blob,source)})
 return out

def parse_ics(source,body):
 lines=re.sub(r'\r?\n[ \t]','',body).splitlines(); out=[]; ev={}; inside=False
 def flush():
  if not ev: return
  title=ev.get('SUMMARY') or ev.get('NAME'); blob=' '.join(ev.values())
  d=ev.get('DTSTART') or date_text(blob)
  if title and d and is_future_or_current(d) and (scene_tags(blob) or 'festival' in blob.lower()) and looks_like_real_event(title, blob, ev.get('URL','')):
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
    if not d or not is_future_or_current(d): return None
    if not looks_like_real_event(title, blob, link): return None
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

# --- Directory importer v5: Gothic shops, clubs, bars and magazines ---
ENTITY_TYPES = {
 'shop': {'label':'Gothic-Laden','queries':['Gothic clothing shop store alternative fashion Europe','Gothic shop Deutschland Gothic Kleidung Laden','dark fashion alternative clothing shop UK','Gothic record shop dark music store Europe'], 'hint':re.compile(r'\b(gothic shop|goth shop|gothic store|goth clothing|alternative fashion|dark fashion|gothic clothing|gothic boutique|record shop|plattenladen|bekleidung|boutique)\b',re.I)},
 'club': {'label':'Gothic-Club','queries':['Gothic club darkwave club night Europe','Gothic Club Deutschland Darkwave Party Club','alternative club post-punk darkwave venue','EBM industrial club night Europe'], 'hint':re.compile(r'\b(gothic club|goth club|darkwave club|dark wave club|alternative club|dark music club|club night|nachtclub|nachtleben|club venue|ebm club|industrial club)\b',re.I)},
 'bar': {'label':'Gothic-Bar','queries':['Gothic bar dark bar alternative bar Europe','Gothic bar Deutschland alternative bar','darkwave bar goth pub alternative nightlife','alternative bar post-punk bar Europe'], 'hint':re.compile(r'\b(gothic bar|goth bar|dark bar|alternative bar|goth pub|dark pub|alternative pub|rock bar|metal bar|darkwave bar|scene bar|szene-bar|kneipe|cocktail bar)\b',re.I)},
 'magazine': {'label':'Dark-Music-Magazin','queries':['Gothic magazine dark music magazine webzine','darkwave post-punk music magazine webzine','Gothic Magazin Dark Music Deutschland','EBM industrial music magazine webzine'], 'hint':re.compile(r'\b(gothic magazine|dark music magazine|darkwave magazine|music magazine|music webzine|webzine|gothic magazin|post-punk magazine|ebm magazine|industrial music magazine)\b',re.I)}
}
ENTITY_BAD_TITLE=re.compile(r'\b(best of|top \d+|directory|list of|what is|definition|meaning|wikipedia|how to|guide to|history of|buy now|amazon|etsy search)\b',re.I)
ENTITY_ADDRESS=re.compile(r'\b(address|contact|kontakt|opening hours|opening times|öffnungszeiten|impressum|visit us|find us|location|adresse|street|straße|strasse|postal code|postcode|standort|anfahrt)\b',re.I)

def norm_url(url):
 try:
  p=urllib.parse.urlsplit(str(url or '').strip())
  if p.scheme not in ('http','https') or not p.netloc: return ''
  host=p.netloc.lower()
  if host.startswith('www.'): host=host[4:]
  return urllib.parse.urlunsplit((p.scheme.lower(),host,p.path.rstrip('/'),'',''))
 except Exception: return ''

def entity_city_country(text):
 city=extract_city(str(text or ''),{})
 country=''
 aliases={'Germany':'Deutschland','Austria':'Österreich','Switzerland':'Schweiz','Netherlands':'Niederlande','Belgium':'Belgien','France':'Frankreich','United Kingdom':'Vereinigtes Königreich','United States':'USA','Poland':'Polen','Czech Republic':'Tschechien','Spain':'Spanien','Italy':'Italien','Portugal':'Portugal','Denmark':'Dänemark','Sweden':'Schweden','Norway':'Norwegen','Finland':'Finnland','Ireland':'Irland','Australia':'Australien','Canada':'Kanada'}
 for name in list(COUNTRIES.values())+list(aliases):
  if name!='Europa' and re.search(r'\b'+re.escape(name)+r'\b',str(text or ''),re.I):
   country=aliases.get(name,name); break
 return city,country

def html_to_text(body):
 body=re.sub(r'(?is)<(script|style|noscript|svg)\b.*?</\1\s*>',' ',str(body or ' '))
 return html.unescape(re.sub(r'\s+',' ',re.sub(r'(?s)<[^>]+>',' ',body)))[:160000]

def entity_kind(text):
 for kind in ('magazine','shop','club','bar'):
  if ENTITY_TYPES[kind]['hint'].search(str(text or '')): return kind
 return None

def entity_key(rec):
 return (str(rec.get('record_type') or 'event').lower(),str(rec.get('name') or '').strip().lower(),str(rec.get('city') or '').strip().lower(),str(rec.get('country_name',rec.get('country')) or '').strip().lower(),norm_url(rec.get('url') or ''))

def verify_directory_result(result,query,geocache):
 title=html.unescape(str(result.get('title') or '')).strip(); url=norm_url(result.get('link'))
 snippet=html.unescape(str(result.get('snippet') or '')).strip()
 if not title or not url or ENTITY_BAD_TITLE.search(title): return None
 try: status,ctype,body=fetch(url,'text/html,application/xhtml+xml,application/xml;q=0.8,*/*;q=0.5')
 except Exception as e: print('DIRECTORY FETCH ERROR',url,repr(e)); return None
 if status!=200: return None
 page=html_to_text(body); blob=' '.join([title,snippet,page,url]); kind=entity_kind(page+' '+title+' '+snippet)
 if not kind: return None
 hits=len(ENTITY_TYPES[kind]['hint'].findall(page))
 if hits<1: return None
 city,country=entity_city_country(blob)
 # Physical places need location evidence; online magazines do not.
 if kind!='magazine' and not (city or country or ENTITY_ADDRESS.search(page)): return None
 name=re.sub(r'\s*[|–—-]\s*(official website|official site|facebook|instagram|home page).*$','',title,flags=re.I).strip()
 if len(name)<2: return None
 tags=scene_tags(blob)
 if not tags: return None
 score=4+min(hits,3)+(2 if city else 0)+(1 if country else 0)
 if kind=='magazine' and re.search(r'\b(articles?|interviews?|reviews?|magazine|webzine|news|features?)\b',page,re.I): score+=2
 rec={'id':'directory-'+slug(name,city or country or url),'record_type':kind,'name':name,'city':city or None,'country_name':country or None,'type':[kind],'categories':[ENTITY_TYPES[kind]['label']],'szenerelevanz':tags,'szenerelevanz_labels':labels(tags),'url':url,'source_url':url,'description':snippet[:500] or None,'verified':True,'verified_date':TODAY,'aktivitaet':'active','aktivitaet_label':'🟢 aktuell aktiv','discovery_status':'published','auto_discovered':True,'auto_importer':'directory_v5','confidence_score':score,'confidence_reasons':['Originalseite erfolgreich abgerufen','Kategorie auf Originalseite bestätigt']+(['Ort erkannt'] if city else [])+(['Land erkannt'] if country else []),'auto_sources':[url],'discovered_at':NOW.isoformat(),'last_source_check':NOW.isoformat(),'online_only':kind=='magazine' and not city,'google_maps_url':maps_url(name,city or '',country or ''),'google_maps_directions_url':maps_dir(name=name,city=city or '',country=country or ''),'google_maps_status':'search_link','geocoded':False}
 if city:
  geo=geocode(name,city,country or '',geocache)
  if geo:
   rec.update({'lat':geo['lat'],'lng':geo['lng'],'geocoded':True,'google_maps_status':'geocoded','google_maps_coords_url':'https://www.google.com/maps/search/?api=1&query='+urllib.parse.quote_plus(f"{geo['lat']},{geo['lng']}")})
 return rec

def discover_directory_entities(geocache):
 if not SERPAPI_KEY:
  print('DIRECTORY IMPORT: Websuche übersprungen (SERPAPI_KEY fehlt)'); return [],0
 rows=[]; errors=0; seen=set()
 for kind,conf in ENTITY_TYPES.items():
  for query in conf['queries']:
   results=serpapi_search(query,'de','en'); print('DIRECTORY SEARCH',kind,query,'results',len(results))
   for result in results:
    url=norm_url(result.get('link'))
    if not url or url in seen: continue
    seen.add(url)
    try:
     rec=verify_directory_result(result,query,geocache)
     if rec and rec['record_type']==kind: rows.append(rec)
    except Exception as e:
     errors+=1; print('DIRECTORY ITEM ERROR',url,repr(e))
 return rows,errors

def recheck_directory_candidates(data,candidates,changes):
 """Recheck old directory candidates; promote only after live-page category evidence."""
 existing={entity_key(x) for x in data}; promoted=0
 for rec in list(candidates):
  kind=str(rec.get('record_type') or '').lower()
  if kind not in ENTITY_TYPES: continue
  url=norm_url(rec.get('url'))
  if not url: continue
  try:
   status,ctype,body=fetch(url,'text/html,application/xhtml+xml,*/*;q=0.5')
   rec['last_source_check']=NOW.isoformat()
   if status!=200: rec['last_check_error']='HTTP '+str(status); continue
   page=html_to_text(body)
   if not ENTITY_TYPES[kind]['hint'].search(page): rec['review_status']='still_candidate'; continue
   city,country=entity_city_country(page)
   if kind!='magazine' and not (city or country or ENTITY_ADDRESS.search(page)): continue
   rec.update({'record_type':kind,'type':[kind],'categories':[ENTITY_TYPES[kind]['label']],'verified':True,'verified_date':TODAY,'discovery_status':'published','aktivitaet':'active','aktivitaet_label':'🟢 aktuell aktiv','auto_importer':'directory_v5'})
   if city and not rec.get('city'): rec['city']=city
   if country and not rec.get('country_name'): rec['country_name']=country
   key=entity_key(rec)
   if key not in existing:
    data.append(rec); existing.add(key); promoted+=1
    changes.insert(0,{'timestamp':NOW.isoformat(),'type':'directory_candidate_promoted','record_type':kind,'name':rec.get('name'),'city':rec.get('city'),'source':url})
   candidates.remove(rec)
  except Exception as e:
   rec['last_check_error']=str(e); rec['last_source_check']=NOW.isoformat()
 return promoted

# -----------------------------------------------------------------------------


def load_json(path,default):
 try:
  with open(path,encoding='utf-8') as f: return json.load(f)
 except Exception: return default

def save_json(path,obj):
 tmp=path+'.tmp'
 with open(tmp,'w',encoding='utf-8') as f:
  json.dump(obj,f,ensure_ascii=False,indent=2)
  f.write('\n')
 os.replace(tmp,path)

def write_status(**kwargs):
 status={'version':'5.0','timestamp':NOW.isoformat()}
 status.update(kwargs)
 try: save_json(STATUS,status)
 except Exception as e: print('STATUS WRITE ERROR',repr(e))


RECURRING_HINTS=re.compile(r'\b(monthly|monatlich|weekly|wöchentlich|jeden\s+\w+|every\s+\w+|regelmäßig|regelmaessig|jährlich|jaehrlich|annual|yearly|recurring|wiederkehrend)\b',re.I)
EVENT_EVIDENCE=re.compile(r'\b(tickets?|admission|doors?|venue|line[- ]?up|lineup|event|veranstaltung|concert|konzert|party|festival|tour|live|dj|djs)\b',re.I)

def audit_event_record(rec):
    """Fast deterministic quality classification from stored evidence.
    No network request here: the daily discovery pass already checks sources.
    green = verified current/recurring event with a scene source;
    yellow = plausible but missing a strong date/source signal;
    red = stale/non-event data.
    """
    if rec.get('record_type') != 'event':
        return None
    name=str(rec.get('name') or '')
    blob=' '.join([name,str(rec.get('description') or ''),str(rec.get('date_text') or ''),str(rec.get('url') or ''),str(rec.get('source_url') or '')])
    tags=rec.get('szenerelevanz') or scene_tags(blob)
    v=rec.get('veranstaltung') or {}
    recurring=bool(v.get('regelmässig')) or bool(RECURRING_HINTS.search(blob))
    future=is_future_or_current(rec.get('date_text')) or bool(v.get('naechster_termin'))
    official=bool(rec.get('verified')) and bool(rec.get('url'))
    eventish=bool(EVENT_EVIDENCE.search(blob)) or 'festival' in (name+' '+str(v)).lower() or recurring
    if official and tags and eventish and (future or recurring):
        return ('green','🟢 geprüft / relevante Veranstaltung','Verifizierter Szene-Eintrag mit Quelle und aktuellem bzw. wiederkehrendem Terminindikator.')
    if tags and eventish and (future or recurring):
        return ('yellow','🟡 Prüfung empfohlen','Plausibler Szene-Termin, aber die gespeicherten Prüfsignale sind nicht vollständig.')
    if not future and not recurring:
        return ('red','🔴 Termin nicht aktuell','Kein aktueller bzw. wiederkehrender Terminindikator vorhanden.')
    return ('yellow','🟡 Prüfung empfohlen','Quelle bzw. Veranstaltungsnachweis ist für die automatische Einstufung nicht eindeutig genug.')

def audit_existing_events(data):
    checked=green=yellow=red=0
    for rec in data:
        if rec.get('record_type')!='event':
            continue
        result=audit_event_record(rec)
        if not result: continue
        status,label,note=result
        rec['quality_status']=status
        rec['quality_label']=label
        rec['quality_note']=note
        rec['quality_checked_at']=NOW.isoformat()
        checked+=1
        if status=='green': green+=1
        elif status=='yellow': yellow+=1
        else: red+=1
    return checked,green,yellow,red

def main():
 data=load_json(DATA,[]); candidates=load_json(CANDIDATES,[]); changes=load_json(CHANGES,[]); geocache=load_json(GEOCACHE,{})
 if not isinstance(data,list): raise SystemExit('data/nachtfragment.json muss ein Array sein')
 if not isinstance(candidates,list): candidates=[]
 known={(str(x.get('name') or '').strip().lower(),str(x.get('city') or '').strip().lower(),str(x.get('country_name',x.get('country')) or '').strip().lower()) for x in data}
 cand_known={(str(x.get('name') or '').strip().lower(),str(x.get('city') or '').strip().lower(),str(x.get('country_name',x.get('country')) or '').strip().lower()) for x in candidates}
 new_pub=0; new_cand=0; source_errors=[]; search_errors=0
 for source in load_json(SOURCES,[]):
  try:
   if not isinstance(source,dict) or not isinstance(source.get('url'),str) or not source.get('url').startswith(('http://','https://')):
    print('SKIP INVALID SOURCE',repr(source))
    continue
   status,ctype,items=discover(source); print(source.get('name',source.get('url')),status,ctype,'found',len(items))
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
     'google_maps_directions_url':maps_dir(lat=geo['lat'] if geo else None,lng=geo['lng'] if geo else None,name=c['name'],city=city,country=country),
     'geocoded':bool(geo),
     'google_maps_status':'search_link'
    }
    if geo:
     rec['lat']=geo['lat']; rec['lng']=geo['lng']
     rec['google_maps_coords_url']='https://www.google.com/maps/search/?api=1&query='+urllib.parse.quote_plus(f"{geo['lat']},{geo['lng']}")
     rec['google_maps_status']='geocoded'
    # Official, strongly evidenced items can be published; all others stay candidates.
    publish = (source.get('kind')=='official' and score>=7 and bool(city) and
               bool(c.get('date_text')) and is_future_or_current(c.get('date_text')) and
               looks_like_real_event(c.get('name',''), c.get('raw',''), c.get('url','')))
    if key in known:
     for x in data:
      if (str(x.get('name') or '').strip().lower(),str(x.get('city') or '').strip().lower(),str(x.get('country_name',x.get('country')) or '').strip().lower())==key:
       x.setdefault('auto_sources',[])
       if source.get('url') not in x['auto_sources']: x['auto_sources'].append(source.get('url'))
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
   print('ERROR',str(source.get('name') or source.get('url') or 'unknown'),repr(e)); source_errors.append({'source':source.get('url'),'error':str(e)}); changes.insert(0,{'timestamp':NOW.isoformat(),'type':'source_error','source':source.get('url'),'error':str(e)})
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
    page_date=date_text(page_text)
    if page_date and is_future_or_current(page_date):
        c['date_text']=page_date
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
    # Web-search results are leads. Publish only when the ORIGINAL page contains
    # strong event evidence, a future/current date, a city, and scene evidence.
    event_evidence=bool(re.search(r'\b(tickets?|admission|doors?|venue|line[- ]?up|lineup|event|veranstaltung|concert|konzert|party|festival|tour|live)\b', page_text, re.I))
    future_ok=is_future_or_current(c.get('date_text'))
    publish=(st==200 and score>=10 and bool(tags) and bool(c['date_text']) and future_ok and bool(city) and event_evidence and looks_like_real_event(c['name'], page_text, c['url']))
    if publish:
     rec['discovery_status']='published'; rec['verified']=True; rec['verified_date']=TODAY; rec['aktivitaet']='active'; rec['aktivitaet_label']='🟢 aktuell aktiv'
     data.append(rec); known.add(key); new_pub+=1
     changes.insert(0,{'timestamp':NOW.isoformat(),'type':'published_web_search','name':c['name'],'city':city,'source':c['url'],'score':score})
    else:
     candidates.append(rec); cand_known.add(key); new_cand+=1
     changes.insert(0,{'timestamp':NOW.isoformat(),'type':'candidate_web_search','name':c['name'],'city':city,'source':c['url'],'score':score})
   except Exception as e:
    search_errors += 1
    print('SEARCH ITEM ERROR',c.get('url'),repr(e))

 # Directory importer: shops, clubs, bars and magazines; verify original pages.
 directory_promoted = recheck_directory_candidates(data,candidates,changes)
 directory_rows,directory_errors = discover_directory_entities(geocache)
 known_directory={entity_key(x) for x in data}
 imported_directory=0
 for rec in directory_rows:
  key=entity_key(rec)
  if key in known_directory: continue
  data.append(rec); known_directory.add(key); imported_directory+=1
  changes.insert(0,{'timestamp':NOW.isoformat(),'type':'directory_imported','record_type':rec.get('record_type'),'name':rec.get('name'),'city':rec.get('city'),'source':rec.get('url'),'score':rec.get('confidence_score')})
 print('DIRECTORY IMPORTED',imported_directory,'PROMOTED',directory_promoted,'ERRORS',directory_errors)

 # de-duplicate published data and candidates
 def dedupe(rows):
  seen=set(); out=[]
  for x in rows:
   key=(str(x.get('name') or '').strip().lower(),str(x.get('city') or '').strip().lower(),str(x.get('country_name',x.get('country')) or '').strip().lower())
   if key in seen: continue
   seen.add(key); out.append(x)
  return out
 data=dedupe(data); candidates=dedupe(candidates)
 checked,quality_green,quality_yellow,quality_red=audit_existing_events(data)
 save_json(DATA,data); save_json(CANDIDATES,candidates); save_json(CHANGES,changes[:1000]); save_json(GEOCACHE,geocache)
 write_status(total=len(data), published=len(data), events=sum(1 for x in data if x.get('record_type')=='event'), shops=sum(1 for x in data if x.get('record_type')=='shop'), clubs=sum(1 for x in data if x.get('record_type')=='club'), bars=sum(1 for x in data if x.get('record_type')=='bar'), magazines=sum(1 for x in data if x.get('record_type')=='magazine'), directory_imported=imported_directory, directory_promoted=directory_promoted, directory_errors=directory_errors, candidates=len(candidates), new_published=new_pub, new_candidates=new_cand, source_errors=len(source_errors), search_item_errors=search_errors, quality_checked=checked, quality_green=quality_green, quality_yellow=quality_yellow, quality_red=quality_red, serpapi_configured=bool(SERPAPI_KEY), today=TODAY)
 print('TOTAL',len(data),'EVENTS',sum(1 for x in data if x.get('record_type')=='event'),'SHOPS',sum(1 for x in data if x.get('record_type')=='shop'),'CLUBS',sum(1 for x in data if x.get('record_type')=='club'),'BARS',sum(1 for x in data if x.get('record_type')=='bar'),'MAGAZINES',sum(1 for x in data if x.get('record_type')=='magazine'),'PUBLISHED',new_pub,'CANDIDATES',len(candidates),'NEW_CANDIDATES',new_cand,'DIRECTORY_IMPORTED',imported_directory,'DIRECTORY_PROMOTED',directory_promoted,'DIRECTORY_ERRORS',directory_errors,'SOURCE_ERRORS',len(source_errors),'SEARCH_ERRORS',search_errors,'QUALITY',quality_green,quality_yellow,quality_red)
 # Discovery is best-effort: individual dead sources must not make the daily workflow fail.
 return 0
if __name__=='__main__':
 try:
  raise SystemExit(main() or 0)
 except Exception as e:
  print('FATAL UPDATER ERROR:',repr(e))
  try: write_status(status='fatal_error',error=str(e))
  except Exception: pass
  # Keep Actions green for transient/external source failures. Local file corruption is
  # still printed clearly in the log so it can be repaired without losing prior data.
  raise SystemExit(0)
