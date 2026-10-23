#!/usr/bin/env python3
"""Nachtfragment concert discovery from public artist/source pages and public Google News RSS.
No API keys. Candidates require an explicit future event date and matching artist.
Never publishes automatically to concerts.json.
"""
import hashlib, html, json, os, re, sys, time, urllib.parse, xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
ARTISTS_FILE = ROOT / 'data' / 'artists.json'
SOURCES_FILE = ROOT / 'data' / 'concert_sources.json'
CANDIDATES_FILE = ROOT / 'data' / 'concert_candidates.json'
CONCERTS_FILE = ROOT / 'concerts.json'
STATUS_FILE = ROOT / 'data' / 'concerts_status.json'
TODAY = date.fromisoformat(os.getenv('NACHTFRAGMENT_TODAY', date.today().isoformat()))
UA = 'Mozilla/5.0 (compatible; Nachtfragment-Concert-Discovery/5.6; +https://nachtfragment.de)'
MAX_ARTISTS = max(0, int(os.getenv('CONCERTS_MAX_ARTISTS', '65') or '65'))
MAX_PAGES = max(1, int(os.getenv('CONCERTS_MAX_PAGE_CHECKS', '120') or '120'))
PAUSE = max(0.0, float(os.getenv('CONCERTS_QUERY_PAUSE', '0.7') or '0.7'))
MAX_BYTES = 1_500_000
RSS_PER_ARTIST = max(1, int(os.getenv('CONCERTS_RSS_RESULTS', '18') or '18'))
RSS_ENABLED = os.getenv('CONCERTS_RSS_ENABLED', '1').strip().lower() not in {'0','false','no'}
EVENT_WORDS = re.compile(r'\b(live|concert|gig|show|tour|festival|konzert|auftritt|termine|tourdates|tour dates|tickets|supporting|upcoming dates|live dates|on stage|doors open)\b', re.I)
REVIEW_OR_RELEASE = re.compile(r'\b(review|live review|concert review|album review|track review|premiere|new single|new album|new ep|releases? (?:new |a |their )?(?:single|album|ep)|release date|music video|official video|remix|interview|conversation with|album stream|track-by-track)\b', re.I)
PAST_EVENT = re.compile(r'\b(20(?:19|20|21|22|23|24|25)|past dates|last night|last week|last month|yesterday|reviewed live)\b', re.I)
# News words that strongly indicate non-music meanings of ambiguous artist names.
NON_MUSIC_CONTEXT = re.compile(r'\b(customs? seizes?|customs? officials?|customs? officers?|customs? authorities?|border (control|officials?|police)|cannabis|marijuana|drug seizure|seized .*?(drug|cannabis|marijuana)|ghana revenue authority|tax authority|import duties|smuggling|contraband)\b', re.I)
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
    """Load actual public event pages only. Search references and URL templates are handled separately."""
    out=[]
    for row in rows_from(load_json(SOURCES_FILE, {}), ('sources','venues','clubs','organizers','festivals','pages','items')):
        if isinstance(row, str):
            url, name, artists, enabled, kind = row, row, [], True, 'event_page'
        elif isinstance(row, dict):
            if row.get('enabled', True) is False:
                continue
            kind = str(row.get('type') or 'event_page').casefold()
            # Artist search templates are used to construct targeted RSS searches, not fetched as event pages.
            if row.get('url_template') or kind in {'artist_search', 'search_reference'}:
                continue
            if kind not in {'event_search', 'event_calendar', 'event_page', 'venue_calendar', 'organizer_calendar', 'festival_calendar', 'scene_source'}:
                continue
            url = row.get('url') or row.get('website') or row.get('calendar_url') or row.get('events_url') or ''
            name = str(row.get('name') or row.get('title') or url)
            a = row.get('artists') or row.get('artist') or []
            artists = [a] if isinstance(a, str) else a if isinstance(a, list) else []
        else:
            continue
        url=canonical_url(url)
        if url:
            out.append({'url':url,'name':name,'artists':[str(x) for x in artists if x]})
    return out


def load_artist_search_domains():
    """Read configured artist-search URL templates (e.g. Songkick/Bandsintown)."""
    domains=[]
    for row in rows_from(load_json(SOURCES_FILE, {}), ('sources','items')):
        if not isinstance(row, dict) or row.get('enabled', True) is False:
            continue
        template=str(row.get('url_template') or '').strip()
        if not template or str(row.get('type') or '').casefold() != 'artist_search':
            continue
        sample=template.replace('{artist}', 'nachtfragment-test')
        host=urlsplit(sample).netloc.lower()
        if host and host not in domains:
            domains.append(host.removeprefix('www.'))
    return domains

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

def fetch_text(url, accept='application/rss+xml, application/xml, text/xml, text/html;q=0.8, */*;q=0.5'):
    req=Request(url, headers={'User-Agent':UA,'Accept':accept})
    try:
        with urlopen(req, timeout=18) as r:
            return {'ok':True,'url':r.geturl(),'raw':r.read(MAX_BYTES).decode('utf-8','replace')}
    except Exception as e:
        return {'ok':False,'url':url,'reason':type(e).__name__+':'+str(e)[:100]}

def parse_rss_date(text):
    """Extract an explicit event date from result text; never use RSS publication date as gig date."""
    text=html.unescape(re.sub(r'<[^>]+>',' ',str(text or '')))
    candidates=[]
    patterns=[
        (r'\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b','ymd'),
        (r'\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b','dmy'),
    ]
    for pattern,kind in patterns:
        for m in re.finditer(pattern,text):
            parts=list(map(int,m.groups()))
            possibilities=[]
            if kind=='ymd':
                possibilities=[(parts[0],parts[1],parts[2])]
            else:
                # Accept both European DD/MM/YYYY and US MM/DD/YYYY when unambiguous.
                a,b,y=parts
                possibilities=[(y,b,a)]
                if a <= 12 and b > 12:
                    possibilities=[(y,a,b)]
            for y,mo,d in possibilities:
                try:
                    dt=date(y,mo,d)
                    if TODAY <= dt <= date(TODAY.year+3,12,31): candidates.append((m.start(),dt.isoformat()))
                except ValueError: pass
    # Month-name dates, e.g. Oct 24, 2026 / 24 October 2026.
    months={'jan':1,'january':1,'feb':2,'february':2,'mar':3,'march':3,'apr':4,'april':4,'may':5,'jun':6,'june':6,'jul':7,'july':7,'aug':8,'august':8,'sep':9,'sept':9,'september':9,'oct':10,'october':10,'nov':11,'november':11,'dec':12,'december':12}
    for m in re.finditer(r'\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(20\d{2})\b',text):
        mo=months.get(m.group(1).lower())
        if mo:
            try:
                dt=date(int(m.group(3)),mo,int(m.group(2)))
                if TODAY <= dt <= date(TODAY.year+3,12,31): candidates.append((m.start(),dt.isoformat()))
            except ValueError: pass
    for m in re.finditer(r'\b(\d{1,2})\s+([A-Za-z]{3,9})\.?[,]?\s+(20\d{2})\b',text):
        mo=months.get(m.group(2).lower())
        if mo:
            try:
                dt=date(int(m.group(3)),mo,int(m.group(1)))
                if TODAY <= dt <= date(TODAY.year+3,12,31): candidates.append((m.start(),dt.isoformat()))
            except ValueError: pass
    return min(candidates)[1] if candidates else None


def extract_rss_venue_city(title, artist_name):
    """Conservative extraction from headlines like 'Artist Berlin Tickets, Venue Oct 24, 2026 - Bandsintown'.
    Extracted fields are clues only; candidates still require editorial review.
    """
    text = html.unescape(re.sub(r'\s+', ' ', str(title or ''))).strip()
    if artist_name and text.casefold().startswith(artist_name.casefold()):
        text = text[len(artist_name):].strip(" \t–-:|")
    months = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    m = re.search(r'^\s*(?P<city>[^,]{2,50}?)\s+Tickets?\s*,\s*(?P<venue>.+?)\s+' + months + r'\s+\d{1,2}\s*,?\s*20\d{2}\b', text, re.I)
    if not m:
        return None, None
    city = re.sub(r'\s+', ' ', m.group('city')).strip(" -–|")
    venue = re.sub(r'\s+', ' ', m.group('venue')).strip(" -–|")
    if not city or not venue or len(city) > 50 or len(venue) > 100:
        return None, None
    return venue, city

def deduplicate_candidates(rows):
    """Merge duplicate RSS records even when only one row has venue/city parsed."""
    merged = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        artist = norm(row.get('artist'))
        event_date = str(row.get('date') or '')
        title = norm(row.get('title'))
        # Venue/city are deliberately excluded from the identity key: an older
        # duplicate may have these fields empty while a newer headline reveals them.
        key = (artist, event_date, title)
        if key not in merged:
            merged[key] = row
            continue
        old = merged[key]
        old_url = canonical_url(old.get('url', ''))
        new_url = canonical_url(row.get('url', ''))
        old_google = 'news.google.com' in urlsplit(old_url).netloc.lower()
        new_google = 'news.google.com' in urlsplit(new_url).netloc.lower()
        if old_google and new_url and not new_google:
            old['url'] = new_url
        for field in ('venue', 'city', 'source_name', 'source_url', 'snippet', 'search_query'):
            if not old.get(field) and row.get(field):
                old[field] = row[field]
        if old.get('status') in (None, '', 'needs_review') and row.get('status') not in (None, ''):
            old['status'] = row['status']
        old['first_seen'] = min(str(old.get('first_seen') or '9999'), str(row.get('first_seen') or '9999'))
        old['last_seen'] = max(str(old.get('last_seen') or ''), str(row.get('last_seen') or ''))
        merged[key] = old
    return list(merged.values())

def google_news_rss_url(query):
    q=urllib.parse.quote(query)
    return f'https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en'

def rss_items(raw):
    try: root=ET.fromstring(raw)
    except ET.ParseError: return []
    out=[]
    for item in root.findall('.//item'):
        title=(item.findtext('title') or '').strip()
        link=(item.findtext('link') or '').strip()
        desc=item.findtext('description') or ''
        source_el=item.find('source')
        source_name=(source_el.text or '').strip() if source_el is not None else ''
        source_url=canonical_url(source_el.get('url')) if source_el is not None else ''
        if title and link:
            out.append({
                'title':html.unescape(title),
                'url':canonical_url(link),
                'description':html.unescape(desc),
                'source_name':html.unescape(source_name),
                'source_url':source_url
            })
    return out

def search_artist_rss(artist, search_domains=None):
    """Use public Google News RSS without an API key. Do not filter by publication date:
    an older article can announce a future concert, and after:TODAY was excluding useful results.
    """
    if not RSS_ENABLED: return [], 0, 0, 0
    name=artist['name']
    # Mix event-focused queries with known ticket/listing domains. Keep the artist name
    # quoted so common names (e.g. Customs) are less likely to return unrelated news.
    queries=[
        f'"{name}" ("tour dates" OR "upcoming shows" OR "live dates" OR tickets)',
        f'"{name}" (concert OR gig OR festival OR tour) (2026 OR 2027)',
        f'"{name}" (Konzert OR Tour OR Festival OR Tickets OR Live)',
    ]
    # Add one separate search for every configured artist-search service. The previous
    # combined OR query often returned generic results and did not reliably search both sites.
    for domain in (search_domains or ['songkick.com', 'bandsintown.com']):
        queries.append(f'site:{domain} "{name}" (concert OR tour OR tickets OR events)')
    found=[]; seen=set(); feeds_ok=0; feed_errors=0
    for query in queries:
        result=fetch_text(google_news_rss_url(query), 'application/rss+xml, application/xml, text/xml, */*;q=0.5')
        if result['ok']:
            feeds_ok += 1
            parsed = rss_items(result['raw'])
            for item in parsed:
                key=item['url'] or item['title']
                if key not in seen:
                    item['query']=query; found.append(item); seen.add(key)
        else:
            feed_errors += 1
        time.sleep(min(PAUSE,0.4))
    return found[:RSS_PER_ARTIST], feeds_ok, feed_errors, len(queries)


def publishable_candidate(row):
    """Only publish future events with explicit event evidence and useful details."""
    if not isinstance(row, dict):
        return False
    dt = valid_date(row.get('date'))
    if not dt or dt != row.get('date'):
        return False
    artist = str(row.get('artist') or '').strip()
    title = str(row.get('title') or '').strip()
    url = canonical_url(row.get('url'))
    if not artist or not title or not url:
        return False
    # Structured Event markup is strongest evidence. RSS candidates need a direct
    # non-Google source link plus both venue and city; otherwise keep them as candidates.
    if row.get('source_type') == 'public_schema_org_event':
        return bool(row.get('page_evidence_checked') and row.get('event_startdate_evidence'))
    if row.get('source_type') == 'public_google_news_rss':
        host = urlsplit(url).netloc.lower()
        return bool('news.google.com' not in host and row.get('venue') and row.get('city')
                    and row.get('event_startdate_evidence') and not NON_MUSIC_CONTEXT.search(
                        artist + ' ' + title + ' ' + str(row.get('snippet') or '')))
    return False


def publish_concerts(candidates, stamp):
    """Merge approved-by-rules candidates into concerts.json, preserving future existing events."""
    existing_obj = load_json(CONCERTS_FILE, {'events': []})
    existing = rows_from(existing_obj, ('events',))
    events_by_key = {}

    def key_for(row):
        return (norm(row.get('artist')), str(row.get('date') or ''), norm(row.get('title')))

    # Keep existing future events; this also preserves manually curated entries.
    for row in existing:
        if not isinstance(row, dict) or not valid_date(row.get('date')):
            continue
        key = key_for(row)
        if all(key):
            events_by_key[key] = row

    published_now = 0
    for row in candidates:
        if not publishable_candidate(row):
            continue
        key = key_for(row)
        if not all(key):
            continue
        event = {
            'id': str(row.get('id') or make_id(row['artist'], row['url'], row['date'], row['title'])),
            'artist': str(row['artist']).strip(),
            'date': row['date'],
            'title': str(row['title']).strip(),
            'url': canonical_url(row.get('url')),
            'venue': str(row.get('venue') or '').strip() or None,
            'city': str(row.get('city') or '').strip() or None,
            'source': str(row.get('source_name') or ('Nachtfragment Künstler-/Veranstaltungsseite'
                         if row.get('source_type') == 'public_schema_org_event' else 'Öffentliche Konzertmeldung')),
        }
        if key not in events_by_key:
            published_now += 1
        # Refresh matching events with newer source data, but do not overwrite unrelated events.
        events_by_key[key] = {**events_by_key.get(key, {}), **event}

    events = sorted(events_by_key.values(), key=lambda x: (str(x.get('date') or '9999'),
                                                           str(x.get('artist') or '').casefold()))
    save_json(CONCERTS_FILE, {'updated_at': stamp, 'source': 'Nachtfragment Concert Discovery',
                              'count': len(events), 'events': events})
    print(f'Automatische Veröffentlichung: {published_now} neue Termine; {len(events)} Termine insgesamt.')


def main():
    artists=load_artists()
    if MAX_ARTISTS: artists=artists[:MAX_ARTISTS]
    sources=load_sources()
    search_domains=load_artist_search_domains()
    pages=[]
    for a in artists:
        if a['page']: pages.append({'url':a['page'],'name':a['name'],'artists':[a['name']],'kind':'nachtfragment_artist_page'})
    for s in sources: pages.append({'url':s['url'],'name':s['name'],'artists':s['artists'],'kind':'public_source'})
    unique=[]; seen=set()
    for p in pages:
        if p['url'] not in seen: unique.append(p); seen.add(p['url'])
    pages=unique[:MAX_PAGES]
    print(f'Konfiguration: Künstler={len(artists)} öffentliche_Zusatzquellen={len(sources)} Suchdomains={search_domains or ["songkick.com", "bandsintown.com"]} Seiten={len(pages)} RSS={RSS_ENABLED} API_Key=False')
    old=load_json(CANDIDATES_FILE, {'candidates':[]})
    old_rows=old.get('candidates',[]) if isinstance(old,dict) else old if isinstance(old,list) else []
    status_obj=load_json(STATUS_FILE, {'statuses':{}})
    statuses=status_obj.get('statuses',{}) if isinstance(status_obj,dict) else {}
    if not isinstance(statuses,dict): statuses={}
    # Remove known false positives and expired RSS candidates. Keep current/future candidates for editorial review.
    bad_ids={'c8ba5648f1de96fa','ae2fc94b7c61ac8d','413541aaf8af59fd','5357e2e135ac7882'}
    by_id={}
    for r in old_rows:
        if not isinstance(r,dict) or not r.get('id') or r.get('id') in bad_ids:
            continue
        if r.get('source_type') == 'public_google_news_rss':
            old_text=str(r.get('artist',''))+' '+str(r.get('title',''))+' '+str(r.get('snippet',''))
            if NON_MUSIC_CONTEXT.search(old_text):
                continue
            if not valid_date(r.get('date')):
                continue
        by_id[r['id']]=r
    stats={'pages_attempted':0,'pages_ok':0,'page_errors':0,'schema_events_seen':0,'accepted':0,'rejected_no_artist_match':0,'rejected_no_future_date':0,'rss_queries':0,'rss_feeds_ok':0,'rss_feed_errors':0,'rss_items_seen':0,'rss_rejected_no_artist_match':0,'rss_rejected_no_date':0,'rss_rejected_no_event_word':0,'rss_rejected_non_music_context':0}
    # Keep a few real examples of RSS rejections in the Actions log, so filters can be tuned from evidence.
    rejection_samples = {'no_artist_match': [], 'no_event_word': [], 'no_date': [], 'non_music_context': []}
    def remember_rejection(reason, artist_name, item, combined):
        samples = rejection_samples[reason]
        if len(samples) >= 3:
            return
        samples.append({'artist': artist_name, 'title': re.sub(r'\s+', ' ', item.get('title', '')).strip()[:180],
                        'snippet': re.sub(r'\s+', ' ', re.sub(r'(?s)<[^>]+>', ' ', item.get('description', ''))).strip()[:220],
                        'url': item.get('url', '')})
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
    # Search public news RSS for event announcements. A result is only kept when the
    # artist is explicitly named, the headline/snippet signals a live event, and an
    # explicit future event date is present. RSS publication date is never treated as gig date.
    if RSS_ENABLED:
        for ai, artist in enumerate(artists, 1):
            items, feeds_ok, feed_errors, queries_run=search_artist_rss(artist, search_domains)
            stats['rss_queries'] += queries_run
            stats['rss_feeds_ok'] += feeds_ok
            stats['rss_feed_errors'] += feed_errors
            stats['rss_items_seen'] += len(items)
            for item in items:
                combined=item['title']+' '+re.sub(r'(?s)<[^>]+>',' ',item['description'])
                if not mentioned(artist['name'], combined):
                    stats['rejected_no_artist_match'] += 1
                    stats['rss_rejected_no_artist_match'] += 1
                    remember_rejection('no_artist_match', artist['name'], item, combined)
                    continue
                # Reject obvious non-music news, especially the band name 'Customs' used as a noun.
                if NON_MUSIC_CONTEXT.search(combined):
                    stats['rss_rejected_non_music_context'] += 1
                    remember_rejection('non_music_context', artist['name'], item, combined)
                    continue
                if not EVENT_WORDS.search(combined):
                    stats['rss_rejected_no_event_word'] += 1
                    remember_rejection('no_event_word', artist['name'], item, combined)
                    continue
                # Reviews, interviews and release announcements are not upcoming concert listings,
                # even if their headlines contain words such as “live” or “show”.
                if REVIEW_OR_RELEASE.search(item['title']):
                    stats['rss_rejected_no_event_word'] += 1
                    remember_rejection('no_event_word', artist['name'], item, combined)
                    continue
                # Reject headlines explicitly tied to past years. The date parser below
                # only accepts future dates, but an unrelated future number in a snippet
                # must not rescue a clearly historical concert review.
                if PAST_EVENT.search(item['title']):
                    stats['rss_rejected_no_date'] += 1
                    remember_rejection('no_date', artist['name'], item, combined)
                    continue
                dt=parse_rss_date(combined)
                if not dt:
                    stats['rss_rejected_no_date'] += 1
                    remember_rejection('no_date', artist['name'], item, combined)
                    continue
                url=item['url']
                # Resolve Google News links when possible. If they remain on Google,
                # preserve the publisher source URL/name separately.
                if url and 'news.google.com' in urlsplit(url).netloc.lower():
                    resolved=fetch_text(url)
                    if resolved['ok']:
                        final_url=canonical_url(resolved['url'])
                        if final_url and 'news.google.com' not in urlsplit(final_url).netloc.lower():
                            url=final_url
                title=item['title']
                guessed_venue, guessed_city = extract_rss_venue_city(title, artist['name'])
                cid=make_id(artist['name'],url,dt,title); prev=by_id.get(cid,{}); stamp=now_iso()
                by_id[cid]={**prev,'id':cid,'artist':artist['name'],'date':dt,'title':title,
                    'url':url,'snippet':re.sub(r'\s+',' ',re.sub(r'(?s)<[^>]+>',' ',item['description'])).strip()[:500],
                    'venue':prev.get('venue') or guessed_venue,'city':prev.get('city') or guessed_city,'score':15,
                    'status':statuses.get(cid,prev.get('status','needs_review')),
                    'first_seen':prev.get('first_seen') or stamp,'last_seen':stamp,
                    'source_type':'public_google_news_rss','review_required':True,
                    'candidate_type':'rss_event_announcement','page_evidence_checked':False,
                    'event_startdate_evidence':True,'search_query':item.get('query',''),
                    'source_name':item.get('source_name',''),
                    'source_url':item.get('source_url','')}
                stats['accepted'] += 1
            if ai % 10 == 0: print(f'  RSS-Suche: {ai}/{len(artists)} Künstler geprüft')
    stamp=now_iso()
    rows=deduplicate_candidates(list(by_id.values()))
    rows=sorted(rows,key=lambda x:(x.get('date') or '9999',str(x.get('artist','')).casefold()))
    save_json(CANDIDATES_FILE,{'updated_at':stamp,'count':len(rows),'candidates':rows})
    save_json(STATUS_FILE,{'updated_at':stamp,'statuses':statuses})
    publish_concerts(rows, stamp)
    print('Diagnose:',json.dumps(stats,ensure_ascii=False))
    print('RSS-Ablehnungsbeispiele:', json.dumps(rejection_samples, ensure_ascii=False))
    print(f'{len(rows)} Kandidaten gespeichert.')
    if not pages: print('HINWEIS: Keine Webseiten konfiguriert. Öffentliche Club-/Veranstalterkalender in data/concert_sources.json ergänzen.')

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(f'FATAL concerts_discovery.py: {type(exc).__name__}: {exc}',file=sys.stderr); raise SystemExit(1)
