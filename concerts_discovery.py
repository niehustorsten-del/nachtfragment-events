#!/usr/bin/env python3
"""Nachtfragment concert discovery: conservative candidate generation, never auto-publishes.
Requires SERPAPI_KEY. Reads data/artists.json and updates data/concert_candidates.json;
keeps editorial statuses and does not touch data/concerts.json.
"""
from __future__ import annotations
import hashlib, html, json, os, re, sys, time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl, urlencode as enc_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent
ARTISTS = ROOT / 'data/artists.json'
CANDIDATES = ROOT / 'data/concert_candidates.json'
STATUS = ROOT / 'data/concerts_status.json'
KEY = os.getenv('SERPAPI_KEY', '').strip()
TODAY = date.fromisoformat(os.getenv('NACHTFRAGMENT_TODAY', date.today().isoformat()))
UA = 'Nachtfragment-Concert-Discovery/3.1 (+https://nachtfragment.de)'
MAX_ARTISTS = int(os.getenv('CONCERTS_MAX_ARTISTS', '10') or '10') # free-tier safe default; 0 = all
PAUSE = float(os.getenv('CONCERTS_QUERY_PAUSE', '1.5') or '1.5')
STATE = ROOT / 'data/concert_discovery_state.json'
SERPAPI_BLOCKED = False

MONTHS = {name.lower(): i for i, names in enumerate([
    ('january','jan'),('february','feb'),('march','mar'),('april','apr'),('may',),
    ('june','jun'),('july','jul'),('august','aug'),('september','sep','sept'),
    ('october','oct'),('november','nov'),('december','dec')], 1) for name in names}
MONTH_PATTERN = '|'.join(sorted(MONTHS, key=len, reverse=True))
DATE_PATTERNS = [
    re.compile(r'(?<!\d)(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)'),
    re.compile(r'(?<!\d)(\d{1,2})[./](\d{1,2})[./](20\d{2})(?!\d)'),
    re.compile(r'\b(\d{1,2})\s+(' + MONTH_PATTERN + r')\.?[,]?\s+(20\d{2})\b', re.I),
    re.compile(r'\b(' + MONTH_PATTERN + r')\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(20\d{2})\b', re.I),
]
EVENT_WORDS = re.compile(r'\b(tour|live|concert|gig|show|festival|tour dates|tickets?|performing|on stage|doors open|venue|support act|with)\b', re.I)
NEGATIVE = re.compile(r'\b(lyrics?|album review|review|meaning|chords?|tabs?|discography|merch(?:andise)?|shop|playlist|reaction|interview|biography|newcomer list|weblinks|wikipedia|fan fiction|music video|official video|album stream)\b', re.I)
GENERIC_TITLES = {'web links','weblinks','home','news','contact','about','discography','lyrics','shop','store','playlist'}
EVENT_DOMAINS = ('songkick.com','bandsintown.com','ticketmaster.','eventbrite.','dice.fm','residentadvisor.net','facebook.com/events','eventim.','ticketweb.','jambase.com','setlist.fm','songkick.')
TRACKING_PARAMS = {'fbclid','gclid','mc_cid','mc_eid','ref','referrer'}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def artist_names(obj):
    if isinstance(obj, list): rows = obj
    elif isinstance(obj, dict): rows = obj.get('artists') or obj.get('bands') or obj.get('acts') or obj.get('items') or []
    else: rows = []
    names = []
    for row in rows:
        if isinstance(row, str): name = row.strip()
        elif isinstance(row, dict): name = str(row.get('name') or row.get('artist') or row.get('title') or '').strip()
        else: continue
        if name and name.casefold() not in GENERIC_TITLES and len(name) < 100:
            names.append(name)
    return list(dict.fromkeys(names))


def canonical_url(url):
    try:
        parts = urlsplit(str(url).strip())
        if parts.scheme not in ('http', 'https') or not parts.netloc: return ''
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not k.lower().startswith('utm_') and k.lower() not in TRACKING_PARAMS]
        path = re.sub(r'/+', '/', parts.path).rstrip('/') or '/'
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, enc_qs(query), ''))
    except Exception:
        return ''


def search_serpapi(query):
    global SERPAPI_BLOCKED
    if SERPAPI_BLOCKED:
        raise RuntimeError('SerpApi für diesen Lauf pausiert (HTTP 429)')
    params = urlencode({'engine':'google', 'q':query, 'api_key':KEY, 'num':10, 'hl':'en'})
    req = Request('https://serpapi.com/search.json?' + params, headers={'User-Agent':UA})
    try:
        with urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except HTTPError as exc:
        if exc.code == 429:
            SERPAPI_BLOCKED = True
            raise RuntimeError('HTTP 429: SerpApi-Kontingent/Rate-Limit erreicht; SerpApi wird für diesen Lauf pausiert') from exc
        raise
    if data.get('error'):
        raise RuntimeError(str(data['error']))
    return [{'title':r.get('title',''), 'link':r.get('link',''),
             'snippet':r.get('snippet',''), 'date_text':r.get('date','')}
            for r in data.get('organic_results', [])]



class _DDGParser(HTMLParser):
    """Small parser for DuckDuckGo HTML results; best-effort fallback, not guaranteed."""
    def __init__(self):
        super().__init__(); self.results=[]; self._link=None; self._title=[]; self._snippet=[]; self._in_title=False; self._in_snippet=False
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        cls=a.get('class','')
        if tag=='a' and ('result__a' in cls):
            self._link=a.get('href',''); self._title=[]; self._in_title=True
        elif 'result__snippet' in cls:
            self._snippet=[]; self._in_snippet=True
    def handle_endtag(self, tag):
        if tag=='a' and self._in_title:
            title=''.join(self._title).strip(); self._in_title=False
            if title and self._link: self.results.append({'title':title,'link':self._link,'snippet':'','date_text':''})
        if self._in_snippet and tag in ('a','div','td'):
            snippet=''.join(self._snippet).strip(); self._in_snippet=False
            if snippet and self.results and not self.results[-1].get('snippet'): self.results[-1]['snippet']=snippet
    def handle_data(self, data):
        if self._in_title: self._title.append(data)
        if self._in_snippet: self._snippet.append(data)

def search_fallback(query):
    """Try public DuckDuckGo HTML results without consuming SerpApi quota."""
    url='https://html.duckduckgo.com/html/?'+urlencode({'q':query})
    req=Request(url, headers={'User-Agent':'Mozilla/5.0 (compatible; Nachtfragment-Concert-Discovery/3.1)'})
    with urlopen(req, timeout=20) as resp:
        page=resp.read().decode('utf-8','replace')
    parser=_DDGParser(); parser.feed(page)
    return parser.results[:8]

def normalized(s):
    s = html.unescape(str(s or '')).casefold()
    return re.sub(r'[^\w]+', ' ', s, flags=re.UNICODE).strip()


def artist_mentioned(artist, text):
    """Token-aware match; avoids e.g. 'art' matching 'artist' and punctuation issues."""
    a, t = normalized(artist), normalized(text)
    if not a or not t: return False
    return re.search(r'(?<!\w)' + re.escape(a).replace(r'\ ', r'\s+') + r'(?!\w)', t) is not None


def extract_dates(text):
    """Extract future dates from snippets, including Google dates without a year.

    Yearless dates are assigned to the next occurrence (this year if still ahead,
    otherwise next year). This is only candidate discovery; it never publishes.
    """
    found = set()
    text = html.unescape(str(text or '')).replace('–', '-').replace('—', '-')
    # Full dates first: ISO, numeric D/M/Y, and English month names.
    for idx, pat in enumerate(DATE_PATTERNS):
        for m in pat.finditer(text):
            try:
                if idx == 0:
                    y, mo, d = map(int, m.groups())
                elif idx == 1:
                    d, mo, y = map(int, m.groups())
                elif idx == 2:
                    d, month, y = m.groups(); mo = MONTHS[month.lower()]; d = int(d); y = int(y)
                else:
                    month, d, y = m.groups(); mo = MONTHS[month.lower()]; d = int(d); y = int(y)
                parsed = date(y, mo, d)
                if TODAY <= parsed <= date(TODAY.year + 3, 12, 31):
                    found.add(parsed.isoformat())
            except (ValueError, KeyError):
                continue
    # Common Google snippets: "Oct 24", "24 Oct", "October 24th".
    no_year_patterns = [
        re.compile(r'\b(' + MONTH_PATTERN + r')\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b', re.I),
        re.compile(r'\b(\d{1,2})\s+(' + MONTH_PATTERN + r')\.?\b', re.I),
    ]
    for idx, pat in enumerate(no_year_patterns):
        for m in pat.finditer(text):
            try:
                if idx == 0:
                    month, d = m.groups(); mo = MONTHS[month.lower()]; d = int(d)
                else:
                    d, month = m.groups(); mo = MONTHS[month.lower()]; d = int(d)
                year = TODAY.year
                try:
                    parsed = date(year, mo, d)
                except ValueError:
                    continue
                if parsed < TODAY:
                    parsed = date(year + 1, mo, d)
                if parsed <= date(TODAY.year + 2, 12, 31):
                    found.add(parsed.isoformat())
            except (ValueError, KeyError):
                continue
    return sorted(found)


def relevance(artist, result):
    title = html.unescape(str(result.get('title') or '')).strip()
    snippet = html.unescape(str(result.get('snippet') or '')).strip()
    url = canonical_url(result.get('link') or '')
    if not title or not url or NEGATIVE.search(title): return -100
    host = urlsplit(url).netloc.lower().removeprefix('www.')
    title_match = artist_mentioned(artist, title)
    body_match = artist_mentioned(artist, snippet)
    url_match = artist_mentioned(artist, urlsplit(url).path.replace('-', ' ').replace('_', ' '))
    # Artist must occur in title, snippet or a meaningful artist/event URL path.
    if not (title_match or body_match or url_match): return -100
    score = 0
    score += 6 if title_match else 0
    score += 3 if body_match else 0
    score += 2 if url_match else 0
    score += 3 if EVENT_WORDS.search(title) else 0
    score += 2 if EVENT_WORDS.search(snippet) else 0
    score += 2 if any(d in host for d in EVENT_DOMAINS) else 0
    score -= 4 if re.search(r'\b(playlist|discography|biography|interview|album|lyrics|review)\b', title, re.I) else 0
    return score


def stable_id(artist, url, event_date):
    # Canonical URL keeps IDs stable across tracking-query changes.
    return hashlib.sha1(f'{normalized(artist)}|{canonical_url(url)}|{event_date}'.encode()).hexdigest()[:16]


def queries_for(artist):
    year = TODAY.year
    # Do not hard-code 2026/2027: the calendar rolls forward automatically.
    return [
        f'"{artist}" (concert OR live OR tour OR festival) {year}',
        f'"{artist}" tour dates {year + 1}',
        f'"{artist}" concerts tickets upcoming',
    ]


def city_hint(text):
    """Conservative city extraction from common 'in CITY' patterns; uncertain values stay blank."""
    text = html.unescape(str(text or ''))
    patterns = [r'\b(?:in|at)\s+([A-Z][A-Za-zÀ-ÿ\'’-]+(?:\s+[A-Z][A-Za-zÀ-ÿ\'’-]+){0,2})\s*,\s*(?:Germany|UK|United Kingdom|France|USA|United States|Netherlands|Belgium|Sweden|Poland|Italy|Spain|Austria|Switzerland)\b',
                r'\b(?:in|at)\s+(Berlin|Hamburg|Leipzig|Dresden|Munich|München|Cologne|Köln|London|Paris|Amsterdam|Warsaw|Prague|Vienna|Wien|New York|Los Angeles)\b']
    for p in patterns:
        m = re.search(p, text)
        if m: return m.group(1).strip()
    return None


def main():
    artist_data = load_json(ARTISTS, {'artists': []})
    artists = artist_names(artist_data)
    # Skip page-heading-like entries that slipped into the artist source.
    artists = [a for a in artists if not re.search(r'newcomer|linkliste|porträt|portrait|rezension|review|top 50|zwischen darkwave', a, re.I)]
    total_artists = len(artists)
    state = load_json(STATE, {'offset': 0})
    offset = int(state.get('offset', 0) or 0) % max(total_artists, 1)
    if MAX_ARTISTS > 0 and total_artists > MAX_ARTISTS:
        artists = (artists[offset:] + artists[:offset])[:MAX_ARTISTS]
        save_json(STATE, {'offset': (offset + MAX_ARTISTS) % total_artists, 'updated_at': now_iso(), 'last_batch': artists})
    print(f'Konfiguration: artists_datei={ARTISTS} vorhanden={ARTISTS.exists()} artists_batch={len(artists)} artists_total={total_artists} offset={offset} key_vorhanden={bool(KEY)} today={TODAY}')
    if not artists:
        print('FEHLER: Keine Künstler in data/artists.json gefunden. Erwartet wird eine Liste unter artists, bands, acts oder items.', file=sys.stderr)
    old = load_json(CANDIDATES, {'candidates': []})
    old_rows = old.get('candidates', []) if isinstance(old, dict) else old if isinstance(old, list) else []
    status_data = load_json(STATUS, {'statuses': {}})
    statuses = status_data.get('statuses', {}) if isinstance(status_data, dict) else {}
    if not isinstance(statuses, dict): statuses = {}
    by_id = {row['id']: row for row in old_rows if isinstance(row, dict) and row.get('id')}
    # Existing IDs/statuses are preserved even if a search fails or a candidate is no longer returned.
    totals = {'queries': 0, 'search_results': 0, 'accepted': 0, 'no_date': 0, 'low_relevance': 0, 'no_event_word': 0, 'serpapi_errors': 0, 'fallback_results': 0}
    for i, artist in enumerate(artists, 1):
        if len(artist) < 2 or NEGATIVE.search(artist):
            continue
        # One focused query per artist per run keeps free search usage low.
        query = f'"{artist}" (concert OR live OR tour OR festival) upcoming'
        totals['queries'] += 1
        results = []
        if KEY and not SERPAPI_BLOCKED:
            try:
                results = search_serpapi(query)
                print(f'  SerpApi: {len(results)} Treffer | {artist}')
            except Exception as exc:
                totals['serpapi_errors'] += 1
                print(f'SerpApi-Fehler für {artist!r}: {exc}', file=sys.stderr)
        # When quota is exhausted (or no key exists), try a public search fallback.
        if not results and (SERPAPI_BLOCKED or not KEY or totals['serpapi_errors'] > 0):
            try:
                results = search_fallback(query)
                totals['fallback_results'] += len(results)
                print(f'  Fallback-Suche: {len(results)} Treffer | {artist}')
            except Exception as exc:
                print(f'Fallback-Suche fehlgeschlagen für {artist!r}: {exc}', file=sys.stderr)
        totals['search_results'] += len(results)
        for result in results:
            score = relevance(artist, result)
            title = html.unescape(str(result.get('title') or '')).strip()
            snippet = html.unescape(str(result.get('snippet') or '')).strip()
            url = canonical_url(result.get('link') or '')
            combined = ' '.join((title, snippet, str(result.get('date_text') or '')))
            if score < 5:
                totals['low_relevance'] += 1; continue
            if not EVENT_WORDS.search(combined):
                totals['no_event_word'] += 1; continue
            dates = extract_dates(combined)
            if not dates:
                totals['no_date'] += 1; continue
            event_date = dates[0]
            cid = stable_id(artist, url, event_date)
            prev = by_id.get(cid, {})
            seen_at = now_iso()
            by_id[cid] = {
                **prev, 'id': cid, 'artist': artist, 'date': event_date,
                'title': title, 'url': url, 'snippet': snippet,
                'venue': prev.get('venue'), 'city': prev.get('city') or city_hint(combined),
                'score': score, 'status': statuses.get(cid, prev.get('status', 'needs_review')),
                'first_seen': prev.get('first_seen') or seen_at, 'last_seen': seen_at,
                'source_type': 'search_result', 'review_required': True,
            }
            totals['accepted'] += 1
        print(f'[{i}/{len(artists)}] {artist}')
        time.sleep(PAUSE)
    if not KEY:
        print('Hinweis: SERPAPI_KEY fehlt; es wurde nur die öffentliche Fallback-Suche versucht.', file=sys.stderr)
    print('Suchdiagnose:', json.dumps(totals, ensure_ascii=False))
    rows = sorted(by_id.values(), key=lambda r: (r.get('date') or '9999', str(r.get('artist','')).casefold(), -int(r.get('score') or 0)))
    stamp = now_iso()
    save_json(CANDIDATES, {'updated_at': stamp, 'count': len(rows), 'candidates': rows})
    save_json(STATUS, {'updated_at': stamp, 'statuses': statuses})
    print(f'{len(rows)} Kandidaten insgesamt gespeichert ({len(rows) - len(old_rows)} neue/aktualisierte IDs). Keine automatische Veröffentlichung in concerts.json.')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'FATAL concerts_discovery.py: {exc}', file=sys.stderr)
        raise SystemExit(1)
