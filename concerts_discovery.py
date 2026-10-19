#!/usr/bin/env python3
"""Nachtfragment concert discovery: free RSS search, conservative candidates only.
Reads data/artists.json; updates data/concert_candidates.json and status. Never publishes to concerts.json.
"""
from __future__ import annotations
import hashlib, html, json, os, re, sys, time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl, quote_plus
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
ARTISTS = ROOT / 'data/artists.json'
CANDIDATES = ROOT / 'data/concert_candidates.json'
STATUS = ROOT / 'data/concerts_status.json'
STATE = ROOT / 'data/concert_discovery_state.json'
TODAY = date.fromisoformat(os.getenv('NACHTFRAGMENT_TODAY', date.today().isoformat()))
UA = 'Mozilla/5.0 (compatible; Nachtfragment-Concert-Discovery/4.2; +https://nachtfragment.de)'
MAX_ARTISTS = int(os.getenv('CONCERTS_MAX_ARTISTS', '10') or '10')
MAX_PAGE_CHECKS = int(os.getenv('CONCERTS_MAX_PAGE_CHECKS', '8') or '8')
PAUSE = float(os.getenv('CONCERTS_QUERY_PAUSE', '1.0') or '1.0')
MONTHS = {name.lower(): i for i, names in enumerate([
 ('january','jan'),('february','feb'),('march','mar'),('april','apr'),('may',),('june','jun'),('july','jul'),('august','aug'),('september','sep','sept'),('october','oct'),('november','nov'),('december','dec')],1) for name in names}
MP='|'.join(sorted(MONTHS,key=len,reverse=True))
DATE_PATTERNS=[re.compile(r'(?<!\d)(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)'),re.compile(r'(?<!\d)(\d{1,2})[./](\d{1,2})[./](20\d{2})(?!\d)'),re.compile(r'\b(?:mon|tue|wed|thu|fri|sat|sun)(?:day)?[,]?\s+(\d{1,2})\s+('+MP+r')\.?[,]?\s+(20\d{2})\b',re.I),re.compile(r'\b(\d{1,2})\s+('+MP+r')\.?[,]?\s+(20\d{2})\b',re.I),re.compile(r'\b('+MP+r')\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(20\d{2})\b',re.I)]
EVENT_WORDS=re.compile(r'\b(tour|live|concert|gig|show|festival|tour dates|tickets?|performing|on stage|doors open|venue|support act|dates announced|world tour)\b',re.I)
NEGATIVE=re.compile(r'\b(lyrics?|album review|review|meaning|chords?|tabs?|discography|merch(?:andise)?|shop|playlist|reaction|interview|biography|newcomer list|weblinks|wikipedia|fan fiction|music video|official video|album stream)\b',re.I)
GENERIC={'web links','weblinks','home','news','contact','about','discography','lyrics','shop','store','playlist'}
EVENT_DOMAINS=('songkick.com','bandsintown.com','ticketmaster.','eventbrite.','dice.fm','residentadvisor.net','facebook.com/events','eventim.','ticketweb.','jambase.com','setlist.fm')
TRACKING={'fbclid','gclid','mc_cid','mc_eid','ref','referrer'}

def now_iso(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def load_json(p, default):
 try: return json.loads(p.read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError): return default
def save_json(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True); tmp=p.with_suffix(p.suffix+'.tmp'); tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); tmp.replace(p)
def artist_names(obj):
 rows=obj if isinstance(obj,list) else (obj.get('artists') or obj.get('bands') or obj.get('acts') or obj.get('items') or []) if isinstance(obj,dict) else []
 out=[]
 for r in rows:
  n=r.strip() if isinstance(r,str) else str(r.get('name') or r.get('artist') or r.get('title') or '').strip() if isinstance(r,dict) else ''
  if n and n.casefold() not in GENERIC and len(n)<100: out.append(n)
 return list(dict.fromkeys(out))
def canonical_url(url):
 try:
  p=urlsplit(str(url).strip())
  if p.scheme not in ('http','https') or not p.netloc:return ''
  q=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in TRACKING]
  return urlunsplit((p.scheme.lower(),p.netloc.lower(),re.sub(r'/+','/',p.path).rstrip('/') or '/',urlencode(q),''))
 except Exception:return ''
def normalized(s): return re.sub(r'[^\w]+',' ',html.unescape(str(s or '')).casefold(),flags=re.UNICODE).strip()
def artist_mentioned(a,t):
 a,t=normalized(a),normalized(t)
 return bool(a and t and re.search(r'(?<!\w)'+re.escape(a).replace(r'\ ',r'\s+')+r'(?!\w)',t))
def rss_search(query, source):
 if source=='Bing RSS': url='https://www.bing.com/search?'+urlencode({'q':query,'format':'rss','count':'10'})
 else: url='https://news.google.com/rss/search?'+urlencode({'q':query,'hl':'en-US','gl':'US','ceid':'US:en'})
 req=Request(url,headers={'User-Agent':UA,'Accept':'application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8'})
 with urlopen(req,timeout=20) as resp: raw=resp.read()
 root=ET.fromstring(raw); results=[]
 for item in root.findall('.//item'):
  title=item.findtext('title') or ''; link=item.findtext('link') or ''; desc=item.findtext('description') or ''; pub=item.findtext('pubDate') or ''
  if source=='Google News RSS':
   # Google News links are redirect URLs; retain them as source links rather than guessing the destination.
   pass
  results.append({'title':html.unescape(re.sub('<[^>]+>',' ',title)).strip(),'link':link.strip(),'snippet':html.unescape(re.sub('<[^>]+>',' ',desc)).strip(),'date_text':pub,'source':source})
 return results[:10]
def search_free(query):
 results=[]; errors=[]; counts={}
 for source in ('Bing RSS','Google News RSS'):
  try:
   got=rss_search(query,source); counts[source]=len(got); results.extend(got)
  except Exception as e:
   counts[source]=0; errors.append(f'{source}: {type(e).__name__}: {e}')
 # deduplicate on canonical link + title
 unique=[]; seen=set()
 for r in results:
  key=(canonical_url(r.get('link')),normalized(r.get('title')))
  if key not in seen: seen.add(key); unique.append(r)
 return unique,counts,errors
def extract_dates(text):
 found=set(); text=html.unescape(str(text or '')).replace('–','-').replace('—','-')
 for idx,p in enumerate(DATE_PATTERNS):
  for m in p.finditer(text):
   try:
    if idx==0:y,mo,d=map(int,m.groups())
    elif idx==1:d,mo,y=map(int,m.groups())
    elif idx in (2,3):
     if idx==2: d,month,y=m.groups()
     else: d,month,y=m.groups()
     mo=MONTHS[month.lower()];d=int(d);y=int(y)
    else:month,d,y=m.groups();mo=MONTHS[month.lower()];d=int(d);y=int(y)
    dt=date(y,mo,d)
    if TODAY<=dt<=date(TODAY.year+3,12,31):found.add(dt.isoformat())
   except (ValueError,KeyError):pass
 return sorted(found)
def relevance(artist,r):
 title=str(r.get('title') or '').strip(); snippet=str(r.get('snippet') or '').strip(); url=canonical_url(r.get('link') or '')
 if not title or not url or NEGATIVE.search(title):return -100
 host=urlsplit(url).netloc.lower().removeprefix('www.'); path=urlsplit(url).path.replace('-',' ').replace('_',' ')
 tm=artist_mentioned(artist,title); bm=artist_mentioned(artist,snippet); um=artist_mentioned(artist,path)
 if not (tm or bm or um):return -100
 return (6 if tm else 0)+(3 if bm else 0)+(2 if um else 0)+(3 if EVENT_WORDS.search(title) else 0)+(2 if EVENT_WORDS.search(snippet) else 0)+(2 if any(d in host for d in EVENT_DOMAINS) else 0)
def page_event_evidence(url):
 """Fetch a small number of likely direct event pages and extract event dates, not article dates."""
 if not url or 'news.google.com' in urlsplit(url).netloc.lower(): return {'dates': [], 'text': '', 'event_dates': []}
 try:
  req=Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml;q=0.9,*/*;q=0.5'})
  with urlopen(req,timeout=12) as resp:
   if 'html' not in (resp.headers.get('Content-Type') or '').lower(): return {'dates': [], 'text': '', 'event_dates': []}
   raw=resp.read(1_000_000).decode('utf-8','replace')
 except Exception:
  return {'dates': [], 'text': '', 'event_dates': []}
 # Extract structured Event startDate values first; these are stronger than dates in article prose.
 event_dates=[]
 for m in re.finditer(r'(?is)"@type"\s*:\s*(?:"Event"|\[[^]]*"Event"[^]]*\]).{0,12000}?"startDate"\s*:\s*"([^" ]+)',raw):
  val=m.group(1)[:10]
  try:
   dt=date.fromisoformat(val)
   if TODAY<=dt<=date(TODAY.year+3,12,31): event_dates.append(dt.isoformat())
  except ValueError: pass
 # Strip scripts/styles and markup before searching visible text for dates and event context.
 cleaned=re.sub(r'(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>',' ',raw)
 text=html.unescape(re.sub(r'(?s)<[^>]+>',' ',cleaned))
 text=re.sub(r'\s+',' ',text)[:100000]
 return {'dates':extract_dates(text),'text':text,'event_dates':sorted(set(event_dates))}

def stable_id(artist,url,event_date):return hashlib.sha1(f'{normalized(artist)}|{canonical_url(url)}|{event_date}'.encode()).hexdigest()[:16]
def city_hint(text):
 pats=[r'\b(?:in|at)\s+([A-Z][A-Za-zÀ-ÿ\'’-]+(?:\s+[A-Z][A-Za-zÀ-ÿ\'’-]+){0,2})\s*,\s*(?:Germany|UK|United Kingdom|France|USA|United States|Netherlands|Belgium|Sweden|Poland|Italy|Spain|Austria|Switzerland)\b',r'\b(?:in|at)\s+(Berlin|Hamburg|Leipzig|Dresden|Munich|München|Cologne|Köln|London|Paris|Amsterdam|Warsaw|Prague|Vienna|Wien|New York|Los Angeles)\b']
 for p in pats:
  m=re.search(p,str(text or ''))
  if m:return m.group(1).strip()
 return None
def main():
 artist_data=load_json(ARTISTS,{'artists':[]}); all_artists=artist_names(artist_data)
 all_artists=[a for a in all_artists if not re.search(r'newcomer|linkliste|porträt|portrait|rezension|review|top 50|zwischen darkwave',a,re.I)]
 total=len(all_artists); state=load_json(STATE,{'offset':0}); offset=int(state.get('offset',0) or 0)%max(total,1)
 artists=(all_artists[offset:]+all_artists[:offset])[:MAX_ARTISTS] if MAX_ARTISTS>0 and total>MAX_ARTISTS else all_artists
 if total and MAX_ARTISTS>0 and total>MAX_ARTISTS:save_json(STATE,{'offset':(offset+MAX_ARTISTS)%total,'updated_at':now_iso(),'last_batch':artists})
 print(f'Konfiguration: artists_datei={ARTISTS} vorhanden={ARTISTS.exists()} artists_batch={len(artists)} artists_total={total} offset={offset} suchmethode=Bing-RSS+Google-News-RSS key_unnoetig=True today={TODAY}')
 if not artists: print('FEHLER: Keine Künstler in data/artists.json gefunden.',file=sys.stderr)
 old=load_json(CANDIDATES,{'candidates':[]}); old_rows=old.get('candidates',[]) if isinstance(old,dict) else old if isinstance(old,list) else []
 sd=load_json(STATUS,{'statuses':{}}); statuses=sd.get('statuses',{}) if isinstance(sd,dict) else {}; statuses=statuses if isinstance(statuses,dict) else {}
 by_id={r['id']:r for r in old_rows if isinstance(r,dict) and r.get('id')}
 totals={'artists_processed':0,'queries':0,'bing_rss_results':0,'google_news_rss_results':0,'search_results':0,'pages_checked':0,'page_fetch_errors_or_skips':0,'accepted':0,'date_found_but_filtered':0,'no_date':0,'low_relevance':0,'no_event_word':0,'source_errors':0,'serpapi_calls':0}
 page_checks_left=max(0,MAX_PAGE_CHECKS)
 for i,artist in enumerate(artists,1):
  if len(artist)<2 or NEGATIVE.search(artist):continue
  query=f'"{artist}" ("tour dates" OR upcoming OR tickets OR concert OR festival) {TODAY.year}'
  totals['queries']+=1; results,counts,errors=search_free(query)
  totals['bing_rss_results']+=counts.get('Bing RSS',0); totals['google_news_rss_results']+=counts.get('Google News RSS',0); totals['search_results']+=len(results); totals['source_errors']+=len(errors); totals['artists_processed']+=1
  for err in errors:print(f'  QUELLFEHLER {artist}: {err}',file=sys.stderr)
  print(f'  Bing RSS: {counts.get("Bing RSS",0)} | Google News RSS: {counts.get("Google News RSS",0)} | zusammen: {len(results)} Treffer | {artist}')
  for r in results:
   score=relevance(artist,r); title=html.unescape(str(r.get('title') or '')).strip(); snippet=html.unescape(str(r.get('snippet') or '')).strip(); url=canonical_url(r.get('link') or '')
   combined=' '.join((title,snippet,str(r.get('date_text') or '')))
   dates=extract_dates(combined)
   eventish=bool(EVENT_WORDS.search(combined) or any(d in urlsplit(url).netloc.lower() for d in EVENT_DOMAINS))
   if score<4:totals['low_relevance']+=1;continue
   # If search snippets lack a date, inspect a limited number of likely event pages.
   page_text=''; page_event_dates=[]
   if not dates and eventish and page_checks_left>0 and url:
    page_checks_left-=1; totals['pages_checked']+=1
    evidence=page_event_evidence(url); page_text=evidence['text']; page_event_dates=evidence['event_dates']
    if not page_text: totals['page_fetch_errors_or_skips']+=1
    dates=page_event_dates or evidence['dates']
    if page_text and not eventish: eventish=bool(EVENT_WORDS.search(page_text))
   if not dates:totals['no_date']+=1;continue
   if not eventish:totals['no_event_word']+=1;continue
   totals['date_found_but_filtered']+=1
   event_date=dates[0]; cid=stable_id(artist,url,event_date); prev=by_id.get(cid,{}); stamp=now_iso()
   by_id[cid]={**prev,'id':cid,'artist':artist,'date':event_date,'title':title,'url':url,'snippet':snippet,'page_evidence_checked':bool(page_text),'event_startdate_evidence':bool(page_event_dates),'venue':prev.get('venue'),'city':prev.get('city') or city_hint(combined),'score':score,'status':statuses.get(cid,prev.get('status','needs_review')),'first_seen':prev.get('first_seen') or stamp,'last_seen':stamp,'source_type':r.get('source','rss_search_result'),'review_required':True,'candidate_type':'dated_event_search_result'}
   totals['accepted']+=1
  print(f'[{i}/{len(artists)}] {artist}'); time.sleep(PAUSE)
 print('Hinweis: SerpApi wird in Version 4.2 nicht aufgerufen; die verbrauchte kostenlose Quote bleibt unberührt.')
 print('Suchdiagnose:',json.dumps(totals,ensure_ascii=False))
 rows=sorted(by_id.values(),key=lambda r:(r.get('date') or '9999',str(r.get('artist','')).casefold(),-int(r.get('score') or 0)))
 stamp=now_iso(); save_json(CANDIDATES,{'updated_at':stamp,'count':len(rows),'candidates':rows}); save_json(STATUS,{'updated_at':stamp,'statuses':statuses})
 print(f'{len(rows)} Kandidaten insgesamt gespeichert ({len(rows)-len(old_rows)} neue/aktualisierte IDs). Keine automatische Veröffentlichung in concerts.json.')
if __name__=='__main__':
 try:main()
 except Exception as exc:print(f'FATAL concerts_discovery.py: {exc}',file=sys.stderr);raise SystemExit(1)
