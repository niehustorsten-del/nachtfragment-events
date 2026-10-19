#!/usr/bin/env python3
"""Nachtfragment concert discovery from public artist/source pages. No RSS/API keys.
Candidates require a structured Schema.org Event with a matching artist and future startDate.
Never publishes automatically to concerts.json.
"""
import hashlib, html, json, os, re, sys, time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
ARTISTS_FILE = ROOT / 'data' / 'artists.json'
SOURCES_FILE = ROOT / 'data' / 'concert_sources.json'
CANDIDATES_FILE = ROOT / 'data' / 'concert_candidates.json'
STATUS_FILE = ROOT / 'data' / 'concerts_status.json'
TODAY = date.fromisoformat(os.getenv('NACHTFRAGMENT_TODAY', date.today().isoformat()))
UA = 'Mozilla/5.0 (compatible; Nachtfragment-Concert-Discovery/5.0; +https://nachtfragment.de)'
MAX_ARTISTS = max(0, int(os.getenv('CONCERTS_MAX_ARTISTS', '65') or '65'))
MAX_PAGES = max(1, int(os.getenv('CONCERTS_MAX_PAGE_CHECKS', '120') or '120'))
PAUSE = max(0.0, float(os.getenv('CONCERTS_QUERY_PAUSE', '0.7') or '0.7'))
MAX_BYTES = 1_500_000
TRACKING = {'fbclid', 'gclid', 'mc_cid', 'mc_eid', 'ref', 'referrer'}
SKIP_NAME = re.compile(r'newcomer|linkliste|weblinks|rezension|review|top\s*50|zwischen darkwave|playlist|porträt|portrait', re.I)

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def load_json(path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError): return default

def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)

def rows_from(obj, keys):
    if isinstance(obj, list): return obj
    if isinstance(obj, dict):
        for k in keys:
            if isinstance(obj.get(k), list): return obj[k]
    return []

def canonical_url(value):
    try:
        p = urlsplit(str(value or '').strip())
        if p.scheme not in ('http', 'https') or not p.netloc: return ''
        q = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in TRACKING]
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', urlencode(q), ''))
    except Exception: return ''

def norm(value):
    return re.sub(r'[^\w]+', ' ', html.unescape(str(value or '')).casefold(), flags=re.UNICODE).strip()

def mentioned(name, text):
    a, t = norm(name), norm(text)
    return bool(a and t and re.search(r'(?<!\w)' + re.escape(a).replace(r'\ ', r'\s+') + r'(?!\w)', t))

def load_artists():
    result, seen = [], set()
    for row in rows_from(load_json(ARTISTS_FILE, {}), ('artists','bands','acts','items')):
        if isinstance(row, str): name, page = row.strip(), ''
        elif isinstance(row, dict):
            name = str(row.get('name') or row.get('artist') or row.get('title') or '').strip()
            page = str(row.get('nachtfragment_url') or row.get('url') or row.get('website') or '').strip()
        else: continue
        if not name or len(name) > 100 or SKIP_NAME.search(name): continue
        # Remove repeated page-title suffixes such as "Sotiria Sotiria – Porträt".
        name = re.sub(r'\s*[–-]\s*(Porträt|Portrait|Playlist|Linkliste).*$','',name,flags=re.I).strip()
        words = name.split()
        if len(words) >= 4 and len(set(w.casefold() for w in words)) <= 2:
            # Only collapse clear duplicate pairs, e.g. "Deus Ex Lumina Deus Ex Lumina".
            half = len(words)//2
            if len(words) % 2 == 0 and [w.casefold() for w in words[:half]] == [w.casefold() for w in words[half:]]:
                name = ' '.join(words[:half])
        key = name.casefold()
        if key not in seen:
            result.append({'name': name, 'page': canonical_url(page)})
            seen.add(key)
    return result

def load_sources():
    out=[]
    for row in rows_from(load_json(SOURCES_FILE, {}), ('sources','venues','clubs','organizers','festivals','pages','items')):
        if isinstance(row, str): url, name, artists = row, row, []
        elif isinstance(row, dict):
            url = row.get('url') or row.get('website') or row.get('calendar_url') or row.get('events_url') or ''
            name = str(row.get('name') or row.get('title') or url)
            a = row.get('artists') or row.get('artist') or []
            artists = [a] if isinstance(a, str) else a if isinstance(a, list) else []
        else: continue
        url=canonical_url(url)
        if url: out.append({'url':url,'name':name,'artists':[str(x) for x in artists if x]})
    return out

def fetch(url):
    req=Request(url, headers={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml;q=0.9,*/*;q=0.5'})
    try:
        with urlopen(req, timeout=18) as r:
            final=r.geturl(); typ=(r.headers.get('Content-Type') or '').lower()
            if 'html' not in typ and 'xhtml' not in typ: return {'ok':False,'reason':'non_html','url':final}
            return {'ok':True,'reason':'ok','url':final,'raw':r.read(MAX_BYTES).decode('utf-8','replace')}
    except HTTPError as e: return {'ok':False,'reason':f'http_{e.code}','url':url}
    except URLError as e: return {'ok':False,'reason':'url_error:'+str(getattr(e,'reason',e))[:100],'url':url}
    except Exception as e: return {'ok':False,'reason':type(e).__name__+':'+str(e)[:100],'url':url}

def jsonld_objects(raw):
    blocks=re.findall(r'(?is)<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script\s*>',raw)
    out=[]
    for b in blocks:
        try:
            x=json.loads(html.unescape(b).strip()); out.extend(x if isinstance(x,list) else [x])
        except (json.JSONDecodeError, TypeError): pass
    return out

def events_in(obj):
    if isinstance(obj,dict):
        typ=obj.get('@type'); types=typ if isinstance(typ,list) else [typ]
        if any(str(t).casefold()=='event' for t in types): yield obj
        for v in obj.values():
            if isinstance(v,(dict,list)): yield from events_in(v)
    elif isinstance(obj,list):
        for v in obj: yield from events_in(v)

def valid_date(value):
    try:
        d=date.fromisoformat(str(value or '')[:10])
        return d.isoformat() if TODAY <= d <= date(TODAY.year+3,12,31) else None
    except ValueError: return None

def venue_city(event):
    loc=event.get('location') or {}
    if isinstance(loc,list): loc=loc[0] if loc else {}
    if not isinstance(loc,dict): return None,None
    addr=loc.get('address') or {}
    city=addr.get('addressLocality') if isinstance(addr,dict) else None
    return (str(loc.get('name')).strip() if loc.get('name') else None, str(city).strip() if city else None)

def performer_names(event):
    p=event.get('performer') or event.get('performers') or []
    if isinstance(p,dict): p=[p]
    return ' '.join(str(x.get('name') or '') if isinstance(x,dict) else str(x) for x in p if isinstance(x,(dict,str)))

def make_id(artist,url,dt,title):
    return hashlib.sha1(f'{norm(artist)}|{canonical_url(url)}|{dt}|{norm(title)}'.encode()).hexdigest()[:16]

def discover_event_links(raw, base_url, artist_name):
    """Find likely official/tour/calendar links on Nachtfragment artist pages."""
    links=[]
    for m in re.finditer(r'(?is)<a\b([^>]*)href=["\']([^"\']+)["\']([^>]*)>(.*?)</a\s*>', raw):
        attrs=(m.group(1) or '')+' '+(m.group(3) or '')
        href=html.unescape(m.group(2)).strip()
        label=re.sub(r'(?s)<[^>]+>',' ',m.group(4))
        label=re.sub(r'\s+',' ',html.unescape(label)).strip()
        url=canonical_url(urljoin(base_url,href))
        if not url or urlsplit(url).netloc.lower().endswith('nachtfragment.de'):
            continue
        host=urlsplit(url).netloc.lower()
        if any(x in host for x in ('facebook.com','instagram.com','tiktok.com','youtube.com','youtu.be','spotify.com','soundcloud.com','bandcamp.com','apple.com','x.com','twitter.com')):
            continue
        clue=(label+' '+href+' '+attrs).casefold()
        if re.search(r'official|website|homepage|tour|live dates|concert|gig|shows|events|calendar|termine|konzert|veranstaltung|auftritt',clue):
            links.append({'url':url,'name':artist_name+' – entdeckte Terminseite','artists':[artist_name],'kind':'discovered_artist_link'})
    return links

def main():
    artists=load_artists()
    if MAX_ARTISTS: artists=artists[:MAX_ARTISTS]
    sources=load_sources()
    pages=[]
    for a in artists:
        if a['page']: pages.append({'url':a['page'],'name':a['name'],'artists':[a['name']],'kind':'nachtfragment_artist_page'})
    for s in sources: pages.append({'url':s['url'],'name':s['name'],'artists':s['artists'],'kind':'public_source'})
    unique=[]; seen=set()
    for p in pages:
        if p['url'] not in seen: unique.append(p); seen.add(p['url'])
    pages=unique[:MAX_PAGES]
    print(f'Konfiguration: Künstler={len(artists)} öffentliche_Zusatzquellen={len(sources)} Seiten={len(pages)} RSS=False API_Key=False')
    old=load_json(CANDIDATES_FILE, {'candidates':[]})
    old_rows=old.get('candidates',[]) if isinstance(old,dict) else old if isinstance(old,list) else []
    status_obj=load_json(STATUS_FILE, {'statuses':{}})
    statuses=status_obj.get('statuses',{}) if isinstance(status_obj,dict) else {}
    if not isinstance(statuses,dict): statuses={}
    # Remove known false positives created by the old RSS search; preserve all other existing candidates.
    bad_ids={'c8ba5648f1de96fa','ae2fc94b7c61ac8d','413541aaf8af59fd'}
    by_id={r['id']:r for r in old_rows if isinstance(r,dict) and r.get('id') and r.get('id') not in bad_ids}
    stats={'pages_attempted':0,'pages_ok':0,'page_errors':0,'schema_events_seen':0,'accepted':0,'rejected_no_artist_match':0,'rejected_no_future_date':0}
    page_index=0
    while page_index < len(pages) and page_index < MAX_PAGES:
        p=pages[page_index]
        n=page_index+1
        page_index += 1
        result=fetch(p['url']); stats['pages_attempted']+=1
        if not result['ok']:
            stats['page_errors']+=1; print(f"  FEHLER {n}/{len(pages)} {p['url']}: {result['reason']}"); continue
        raw=result['raw']; final=canonical_url(result['url']) or p['url']; found=[]
        if p.get('kind') == 'nachtfragment_artist_page':
            for discovered in discover_event_links(raw, final, p['name']):
                if discovered['url'] not in seen and len(pages) < MAX_PAGES:
                    pages.append(discovered); seen.add(discovered['url'])
        for obj in jsonld_objects(raw): found.extend(events_in(obj))
        stats['pages_ok']+=1; stats['schema_events_seen']+=len(found)
        for ev in found:
            title=html.unescape(str(ev.get('name') or ev.get('headline') or '')).strip()
            performer=performer_names(ev)
            # Prefer explicit performer metadata. If it exists but does not match, do not
            # infer the act from generic title words (important for names such as Customs).
            if performer.strip():
                artist=next((a['name'] for a in artists if mentioned(a['name'], performer)),None)
                if not artist:
                    artist=next((str(a) for a in p.get('artists',[]) if mentioned(str(a), performer)),None)
            else:
                artist=next((a['name'] for a in artists if mentioned(a['name'], title) and re.search(r'\b(live|concert|gig|show|tour|festival|konzert|auftritt)\b', title, re.I)),None)
                if not artist:
                    artist=next((str(a) for a in p.get('artists',[]) if mentioned(str(a), title) and re.search(r'\b(live|concert|gig|show|tour|festival|konzert|auftritt)\b', title, re.I)),None)
            if not artist:
                stats['rejected_no_artist_match']+=1; continue
            dt=valid_date(ev.get('startDate'))
            if not dt:
                stats['rejected_no_future_date']+=1; continue
            venue,city=venue_city(ev); cid=make_id(artist,final,dt,title); prev=by_id.get(cid,{}); stamp=now_iso()
            by_id[cid]={**prev,'id':cid,'artist':artist,'date':dt,'title':title or f'{artist} – Konzert','url':final,
                'snippet':performer or p['name'],'venue':venue or prev.get('venue'),'city':city or prev.get('city'),'score':20,
                'status':statuses.get(cid,prev.get('status','needs_review')),'first_seen':prev.get('first_seen') or stamp,'last_seen':stamp,
                'source_type':'public_schema_org_event','review_required':True,'candidate_type':'structured_event',
                'page_evidence_checked':True,'event_startdate_evidence':True}
            stats['accepted']+=1
        print(f"  OK {n}/{len(pages)} {p['url']} | Schema.org-Events: {len(found)}")
        if PAUSE: time.sleep(PAUSE)
    stamp=now_iso(); rows=sorted(by_id.values(),key=lambda x:(x.get('date') or '9999',str(x.get('artist','')).casefold()))
    save_json(CANDIDATES_FILE,{'updated_at':stamp,'count':len(rows),'candidates':rows})
    save_json(STATUS_FILE,{'updated_at':stamp,'statuses':statuses})
    print('Diagnose:',json.dumps(stats,ensure_ascii=False))
    print(f'{len(rows)} Kandidaten gespeichert. Keine automatische Veröffentlichung in concerts.json.')
    if not pages: print('HINWEIS: Keine Webseiten konfiguriert. Öffentliche Club-/Veranstalterkalender in data/concert_sources.json ergänzen.')

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(f'FATAL concerts_discovery.py: {type(exc).__name__}: {exc}',file=sys.stderr); raise SystemExit(1)
