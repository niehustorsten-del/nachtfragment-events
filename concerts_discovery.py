#!/usr/bin/env python3
"""Nachtfragment concert discovery (add-on; never publishes events automatically).
Searches artist-specific concert/tour results through SerpApi, filters obvious noise,
extracts future dates and keeps candidate IDs stable so editorial decisions survive runs.
Environment: SERPAPI_KEY (required for web search), NACHTFRAGMENT_TODAY (optional test date).
"""
from __future__ import annotations
import hashlib, json, os, re, sys, time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
ARTISTS = ROOT / 'data/artists.json'
CANDIDATES = ROOT / 'data/concert_candidates.json'
STATUS = ROOT / 'data/concerts_status.json'
KEY = os.getenv('SERPAPI_KEY', '').strip()
TODAY = date.fromisoformat(os.getenv('NACHTFRAGMENT_TODAY', date.today().isoformat()))
UA = 'Nachtfragment-Concert-Discovery/2.0 (+https://nachtfragment.de)'

MONTHS = {name.lower(): i for i, names in enumerate([
    ('january','jan'),('february','feb'),('march','mar'),('april','apr'),('may',),
    ('june','jun'),('july','jul'),('august','aug'),('september','sep','sept'),
    ('october','oct'),('november','nov'),('december','dec')], 1) for name in names}
DATE_PATTERNS = [
    re.compile(r'(?<!\d)(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)'),
    re.compile(r'(?<!\d)(\d{1,2})[./](\d{1,2})[./](20\d{2})(?!\d)'),
    re.compile(r'\b(\d{1,2})\s+(' + '|'.join(MONTHS) + r')\.?[,]?\s+(20\d{2})\b', re.I),
    re.compile(r'\b(' + '|'.join(MONTHS) + r')\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(20\d{2})\b', re.I),
]
POSITIVE = re.compile(r'\b(tour|live|concert|gig|show|festival|tour dates|on stage|tickets|performing|supporting|with)\b', re.I)
NEGATIVE = re.compile(r'\b(lyrics|album review|review|meaning|chords|tabs|discography|merch|shop|playlist|reaction|interview|newcomer list|weblinks|wikipedia|fan fiction)\b', re.I)
GENERIC_TITLES = {'web links','weblinks','home','news','contact','about','discography','lyrics','shop','store','playlist'}

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return default

def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def artist_names(obj):
    if isinstance(obj, list): rows = obj
    elif isinstance(obj, dict): rows = obj.get('artists', [])
    else: rows = []
    out=[]
    for row in rows:
        if isinstance(row, str): name=row.strip()
        elif isinstance(row, dict): name=str(row.get('name') or row.get('artist') or row.get('title') or '').strip()
        else: continue
        if name and name.casefold() not in GENERIC_TITLES and len(name) < 100:
            out.append(name)
    return list(dict.fromkeys(out))

def search_serpapi(query):
    params=urlencode({'engine':'google','q':query,'api_key':KEY,'num':10,'hl':'en'})
    req=Request('https://serpapi.com/search.json?'+params, headers={'User-Agent':UA})
    with urlopen(req, timeout=30) as resp:
        data=json.loads(resp.read().decode('utf-8'))
    rows=[]
    for r in data.get('organic_results', []):
        rows.append({'title':r.get('title',''), 'link':r.get('link',''),
                     'snippet':r.get('snippet',''), 'date_text':r.get('date','')})
    return rows

def extract_dates(text):
    found=[]
    for pidx, pat in enumerate(DATE_PATTERNS):
        for m in pat.finditer(text or ''):
            try:
                if pidx == 0: y, mo, d = map(int, m.groups())
                elif pidx == 1: d, mo, y = map(int, m.groups())
                elif pidx == 2: d, month, y = m.groups(); mo=MONTHS[month.lower()]; d=int(d); y=int(y)
                else: month, d, y = m.groups(); mo=MONTHS[month.lower()]; d=int(d); y=int(y)
                parsed=date(y,mo,d)
                if parsed >= TODAY and parsed.year <= TODAY.year + 3:
                    found.append(parsed.isoformat())
            except (ValueError, KeyError):
                pass
    return sorted(set(found))

def relevance(artist, result):
    title=str(result.get('title') or '')
    snippet=str(result.get('snippet') or '')
    url=str(result.get('link') or '')
    blob=f'{title} {snippet} {url}'
    score=0
    if artist.casefold() in blob.casefold(): score += 4
    if POSITIVE.search(blob): score += 3
    if re.search(r'\b(20\d{2}|\d{1,2}[./-]\d{1,2})\b', blob): score += 2
    if any(x in url.casefold() for x in ('songkick.com','bandsintown.com','ticketmaster.','eventbrite.','dice.fm','residentadvisor.net','facebook.com/events','eventim.','ticketweb.')): score += 2
    if NEGATIVE.search(title): score -= 5
    if len(title.strip()) < 5: score -= 2
    if not url.startswith(('http://','https://')): score -= 4
    return score

def stable_id(artist, url, event_date):
    return hashlib.sha1(f'{artist.casefold()}|{url}|{event_date or ""}'.encode()).hexdigest()[:14]

def main():
    artist_data=load_json(ARTISTS, {'artists':[]})
    artists=artist_names(artist_data)
    old=load_json(CANDIDATES, {'candidates':[]})
    old_rows=old.get('candidates', []) if isinstance(old,dict) else old if isinstance(old,list) else []
    status_data=load_json(STATUS, {'statuses':{}})
    statuses=status_data.get('statuses', {}) if isinstance(status_data,dict) else {}
    by_id={}
    for row in old_rows:
        if isinstance(row,dict) and row.get('id'): by_id[row['id']]=row
    if not KEY:
        print('SERPAPI_KEY fehlt: keine Suche ausgeführt; vorhandene Kandidaten bleiben erhalten.', file=sys.stderr)
    else:
        for i, artist in enumerate(artists,1):
            if len(artist) < 2 or NEGATIVE.search(artist):
                continue
            queries=[f'"{artist}" (tour OR live OR concert) 2026', f'"{artist}" tour dates 2027', f'"{artist}" concerts tickets upcoming']
            for query in queries:
                try: results=search_serpapi(query)
                except Exception as exc:
                    print(f'Suche fehlgeschlagen für {artist!r}: {exc}', file=sys.stderr); continue
                for r in results:
                    score=relevance(artist,r)
                    if score < 5: continue
                    combined=' '.join([r.get('title',''),r.get('snippet',''),r.get('date_text','')])
                    dates=extract_dates(combined)
                    if not dates: continue
                    for event_date in dates:
                        cid=stable_id(artist,r.get('link',''),event_date)
                        prev=by_id.get(cid,{})
                        by_id[cid]={**prev, 'id':cid, 'artist':artist, 'date':event_date,
                            'title':r.get('title','').strip(), 'url':r.get('link',''),
                            'snippet':r.get('snippet','').strip(), 'venue':prev.get('venue'),
                            'city':prev.get('city'), 'score':score,
                            'status':statuses.get(cid, prev.get('status','needs_review')),
                            'first_seen':prev.get('first_seen') or datetime.now(timezone.utc).isoformat(timespec='seconds'),
                            'last_seen':datetime.now(timezone.utc).isoformat(timespec='seconds')}
                time.sleep(0.4)
            print(f'[{i}/{len(artists)}] {artist}')
    rows=sorted(by_id.values(), key=lambda r:(r.get('date') or '9999', str(r.get('artist','')).casefold(), -int(r.get('score',0))))
    save_json(CANDIDATES, {'updated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'), 'count':len(rows), 'candidates':rows})
    # Status file is deliberately separate: editorial decisions are never erased by discovery.
    save_json(STATUS, {'updated_at':datetime.now(timezone.utc).isoformat(timespec='seconds'), 'statuses':statuses})
    print(f'{len(rows)} Kandidaten gespeichert. Keine automatische Veröffentlichung in concerts.json.')

if __name__ == '__main__': main()
