#!/usr/bin/env python3
"""Conservative US OLED handheld deals watcher. Python 3.11+, stdlib only.

Never treats a search snippet, RSS headline, crossed-out price or variant's
starting price as a purchasable offer. Only merchant-confirmed SKU/variant,
USD price and stock can generate an exceptional deal alert.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

TIMEOUT = 15
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; LatentViceHandheldDealWatch/1.0; personal-price-monitor)', 'Accept': 'application/json,text/html,application/xml;q=0.8,*/*;q=0.6'}
TAX = 0.08  # NY estimate only; NOT a tax quote
END = dt.date(2026, 11, 15)
MODELS = {
    'legion_go_2_z2e_32': {'label': 'Legion Go 2 Z2 Extreme 32GB', 'watch': 1100, 'exceptional': 1000},
    'onexfly_f1_pro_hx370_32': {'label': 'OneXFly F1 Pro HX 370 32GB', 'watch': 925, 'exceptional': 850},
    'rog_xbox_ally_x20': {'label': 'ROG Xbox Ally X20 (2026 OLED, 24GB)', 'watch': 1100, 'exceptional': 1000},
    'zotac_zone': {'label': 'ZOTAC Zone OLED', 'watch': 575, 'exceptional': 500},
    'steam_deck_oled_512': {'label': 'Steam Deck OLED 512GB', 'watch': 625, 'exceptional': 550},
}
# Deterministic first-party stores, not search-result redirects or marketplace sellers.
SHOPS = [
    {'kind': 'shopify', 'url': 'https://onexplayerstore.com/products/onexfly-f1-pro-wolrd-s-first-amd-ai-370-oled-144hz-gaming-handheld-console', 'seller': 'ONEXPLAYER official', 'condition': 'new', 'shipping': 0},
    {'kind': 'shopify', 'url': 'https://onexplayerstore.com/collections/all-products/products/refurbish-onexfly-f1-pro-oled-144hz-ultimate-gaming-handheld-console-us-stocks', 'seller': 'ONEXPLAYER official', 'condition': 'manufacturer refurbished', 'shipping': 0},
    {'kind': 'html', 'url': 'https://www.bestbuy.com/product/legion-go-2-8-8-144hz-2k-oled-gaming-handheld-amd-ryzen-z2-extreme-32gb-1tb-windows/JJGH3YZPLW/sku/6643145', 'seller': 'Best Buy', 'condition': 'new', 'shipping': None},
    {'kind': 'html', 'url': 'https://www.bestbuy.com/product/legion-go-2-8-8-144hz-2k-oled-gaming-handheld-amd-ryzen-z2-extreme-32gb-1tb/JJGH3YZPLW/sku/6643145/openbox?condition=excellent', 'seller': 'Best Buy', 'condition': 'open-box excellent', 'shipping': None},
    {'kind': 'html', 'url': 'https://www.bestbuy.com/product/legion-go-2-8-8-144hz-2k-oled-gaming-handheld-amd-ryzen-z2-extreme-32gb-1tb/JJGH3YZPLW/sku/6643145/openbox?condition=good', 'seller': 'Best Buy', 'condition': 'open-box good', 'shipping': None},
    {'kind': 'html', 'url': 'https://www.bestbuy.com/product/legion-go-2-8-8-144hz-2k-oled-gaming-handheld-amd-ryzen-z2-extreme-32gb-1tb/JJGH3YZPLW/sku/6643145/openbox?condition=fair', 'seller': 'Best Buy', 'condition': 'open-box fair', 'shipping': None},
    {'kind': 'html', 'url': 'https://rog.asus.com/us/gaming-handhelds/rog-ally/rog-xbox-ally-x20-2026/', 'seller': 'ASUS official', 'condition': 'new', 'shipping': None},
    {'kind': 'html', 'url': 'https://www.zotacstore.com/us/gaming-console', 'seller': 'ZOTAC official', 'condition': 'open-box', 'shipping': None},
    {'kind': 'html', 'url': 'https://store.steampowered.com/steamdeck', 'seller': 'Valve official', 'condition': 'new', 'shipping': None},
]
FEEDS = [
    'https://slickdeals.net/newsearch.php?' + urlencode({'q': q, 'searcharea': 'deals', 'rss': '1'})
    for q in ['legion go 2', 'onexfly f1 pro', 'xbox ally x20', 'zotac zone', 'steam deck oled']
] + ['https://www.reddit.com/r/buildapcsales/new/.rss', 'https://www.reddit.com/r/SteamDeck/new/.rss']
BAD_TERMS = re.compile(r'\b(case|shell|screen protector|charger|replacement part|motherboard|repair|for parts|not working|broken|display only)\b', re.I)


def fetch(url: str) -> str:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=TIMEOUT) as res:
        if res.status != 200:
            raise RuntimeError(f'HTTP {res.status}')
        return res.read(2_000_000).decode('utf-8', errors='replace')


def product_model(s: str) -> str | None:
    s = re.sub(r'[_‐‑–—]', ' ', s.casefold())
    if BAD_TERMS.search(s):
        return None
    if ('legion go 2' in s or 'legion go gen 2' in s) and ('z2 extreme' in s or '83n0000bus' in s) and re.search(r'\b32\s?g(?:b)?\b', s):
        return 'legion_go_2_z2e_32'
    if re.search(r'one\s?x\s?fly\s*f1\s*pro', s) and re.search(r'(?:hx\s?370|ai\s?9\s*370)', s) and re.search(r'\b32\s?g(?:b)?\b', s):
        return 'onexfly_f1_pro_hx370_32'
    if ('ally x20' in s or 'rc74xa' in s) and ('oled' in s or 'rc74xa' in s):
        return 'rog_xbox_ally_x20'
    if ('zotac' in s and 'zone' in s) and ('oled' in s or '8840u' in s):
        return 'zotac_zone'
    if 'steam deck' in s and 'oled' in s and re.search(r'\b512\s?g(?:b)?\b', s):
        return 'steam_deck_oled_512'
    return None


def deal(spec: dict, name: str, price: float, availability: bool, *, variant: str = '') -> dict | None:
    if not availability or price <= 0:
        return None
    model = product_model(f'{name} {variant}')
    if not model:
        return None
    # Product model identity is strongest only for complete SKU / variant.
    shipping = spec['shipping']
    total = round(price + shipping, 2) if shipping is not None else None
    level = ('exceptional' if total is not None and total <= MODELS[model]['exceptional'] else
             'watch' if total is not None and total <= MODELS[model]['watch'] else 'seen')
    return {'model': model, 'label': MODELS[model]['label'], 'title': (name + ' ' + variant).strip(),
            'seller': spec['seller'], 'condition': spec['condition'], 'price': round(price, 2),
            'shipping': shipping, 'before_tax': total, 'estimated_total': round(total * (1 + TAX), 2) if total is not None else None,
            'in_stock': True, 'url': spec['url'], 'level': level, 'evidence': spec['kind']}


def scan_shopify(spec: dict, body: str) -> list[dict]:
    data = json.loads(body)
    title = str(data.get('title') or '')
    # A Shopify "from $999" product price is never used; actual variants only.
    if 'f1 pro' not in title.lower() and 'onexfly' not in title.lower():
        return []
    ret = []
    for v in data.get('variants', []):
        variant = str(v.get('public_title') or v.get('title') or '')
        price = v.get('price')
        if not isinstance(price, (int, float)) or isinstance(price, bool):
            continue
        entry = deal(spec, title, price / 100, v.get('available') is True, variant=variant)
        if entry:
            # Link to actual variant, not default 8840U/HX365 selection.
            entry['url'] = spec['url'].split('?')[0] + '?variant=' + str(v['id'])
            entry['evidence'] = 'shopify variant ID and available=true'
            ret.append(entry)
    return ret


def jsonld_objects(body: str):
    for m in re.finditer(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', body, flags=re.I | re.S):
        try:
            data = json.loads(m.group(1).strip())
            stack = [data]
            while stack:
                obj = stack.pop()
                if isinstance(obj, list):
                    stack.extend(obj)
                elif isinstance(obj, dict):
                    yield obj
                    stack.extend(obj.get('@graph', []) if isinstance(obj.get('@graph'), list) else [])
        except (ValueError, TypeError):
            continue


def scan_html(spec: dict, body: str) -> list[dict]:
    ret = []
    for p in jsonld_objects(body):
        typ = p.get('@type', '')
        if not (typ == 'Product' or (isinstance(typ, list) and 'Product' in typ)):
            continue
        title = str(p.get('name', ''))
        sku = str(p.get('sku') or p.get('mpn') or '')
        for offer in (p.get('offers') if isinstance(p.get('offers'), list) else [p.get('offers')]):
            if not isinstance(offer, dict):
                continue
            if str(offer.get('priceCurrency', '')).upper() != 'USD':
                continue
            # Don't infer available from a buy button. Explicit schema InStock only.
            if not str(offer.get('availability', '')).rstrip('/').lower().endswith('/instock'):
                continue
            if 'bestbuy.com' in urlparse(spec['url']).hostname and sku and sku not in ('6643145', '83N0000BUS'):
                continue
            try:
                price = float(offer['price'])
            except (KeyError, TypeError, ValueError):
                continue
            entry = deal(spec, title + ' ' + sku, price, True)
            if entry:
                # Shipping not confirmed at checkout for these retailers: log for review, never auto-alert.
                ret.append(entry)
    return ret


def feed_discovery(url: str, body: str) -> list[dict]:
    root = ET.fromstring(body)
    results = []
    for item in list(root.findall('.//item')) + list(root.findall('{http://www.w3.org/2005/Atom}entry')):
        title = (item.findtext('title') or item.findtext('{http://www.w3.org/2005/Atom}title') or '').strip()
        if not re.search(r'legion\s+go\s*2|onexfly|ally\s*x20|zotac\s+zone|steam\s+deck\s+oled', title, re.I):
            continue
        link = item.findtext('link') or ''
        if not link:
            e = item.find('{http://www.w3.org/2005/Atom}link')
            link = e.get('href', '') if e is not None else ''
        results.append({'title': title[:200], 'url': link, 'source': urlparse(url).hostname,
                        'status': 'unverified discovery only, never auto-notify'})
    return results[:25]


def issue_marker(entry: dict) -> str:
    canonical = f"{entry['model']}|{entry['url']}|{entry['condition']}"
    return hashlib.sha256(canonical.encode()).hexdigest()[:20]


def api_request(url: str, method: str = 'GET', payload: dict | None = None):
    token = os.environ['GITHUB_TOKEN']
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'LatentViceDealWatch'}
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, method=method, data=data, headers=headers)
    with urlopen(req, timeout=TIMEOUT) as res:
        return json.loads(res.read().decode())


def send_ntfy(entry: dict):
    topic = os.getenv('NTFY_TOPIC', '').strip()
    if not topic:
        return
    if not re.fullmatch(r'[a-zA-Z0-9_-]{16,100}', topic):
        raise ValueError('NTFY_TOPIC must be a random non-public topic (16-100 safe characters)')
    text = f"{entry['label']} ${entry['before_tax']:.2f} + est. 8% NY tax = ${entry['estimated_total']:.2f}; {entry['condition']}; {entry['seller']}. Verify checkout, returns and warranty."
    req = Request(f'https://ntfy.sh/{topic}', data=text.encode(), method='POST',
                  headers={'Title': 'Exceptional OLED handheld deal', 'Priority': 'high', 'Click': entry['url']})
    with urlopen(req, timeout=TIMEOUT) as response:
        if response.status not in (200, 201, 202):
            raise RuntimeError('ntfy failed')


def report_issue(entry: dict) -> str:
    """Create one issue per listing/price; dedupe even across ephemeral Actions runners."""
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if not repo or not os.environ.get('GITHUB_TOKEN'):
        return 'not sent (missing GitHub runtime or token)'
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
        raise ValueError('Invalid GITHUB_REPOSITORY')
    base = f'https://api.github.com/repos/{repo}'
    marker = issue_marker(entry)
    issue_title = f"[Handheld deal] {entry['label']} ${entry['before_tax']:.2f} - {entry['seller']}"
    # One issue per listing: if lower price returns, comment and re-open.
    issues = api_request(base + '/issues?' + urlencode({'state': 'all', 'per_page': '100'}))
    for issue in issues:
        if f'<!-- handheld-deal:{marker} -->' in (issue.get('body') or ''):
            m = re.search(r'<!-- initial-cents:(\d+) -->', issue.get('body') or '')
            old = int(m.group(1)) if m else 10**10
            if round(entry['before_tax'] * 100) >= old - 2500:
                return 'already alerted at this or similar price'
            api_request(base + f"/issues/{issue['number']}/comments", 'POST', {'body': f"Better price now ${entry['before_tax']:.2f} before tax: {entry['url']}"})
            if issue.get('state') == 'closed':
                api_request(base + f"/issues/{issue['number']}", 'PATCH', {'state': 'open'})
            send_ntfy(entry)
            return f"commented on issue #{issue['number']} (price improved)"
    body = (f"<!-- handheld-deal:{marker} -->\n<!-- initial-cents:{round(entry['before_tax'] * 100)} -->\n"
            f"## {entry['label']} — exceptional listing\n\n**Merchant:** {entry['seller']}  \n"
            f"**Condition:** {entry['condition']}  \n**Exact listing:** {entry['url']}  \n"
            f"**Listed:** ${entry['price']:.2f}  \n**US shipping estimate:** ${entry['shipping']:.2f}  \n"
            f"**Before tax including shipping:** ${entry['before_tax']:.2f}  \n"
            f"**With approximate 8% NY sales tax:** ${entry['estimated_total']:.2f}  \n"
            f"**Evidence:** {entry['evidence']}  \n\n"
            "⚠️ Verify stock, local tax, return terms, warranty and checkout total immediately. Price may change. "
            "No purchase has been made. The tracker intentionally excludes eBay auctions and search snippets.\n")
    issue = api_request(base + '/issues', 'POST', {'title': issue_title, 'body': body})
    try:
        send_ntfy(entry)
    except Exception as exc:
        print(f'WARNING: issue created but ntfy failed: {exc}', file=sys.stderr)
    return f"created issue #{issue['number']}"


def scan() -> dict:
    result = {'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'merchants': [],
              'offers': [], 'discovery': [], 'errors': [], 'alerts': []}
    for spec in SHOPS:
        try:
            # Shopify product endpoint returns per-variant exact price and availability.
            url = spec['url'].split('?')[0] + '.js' if spec['kind'] == 'shopify' else spec['url']
            body = fetch(url)
            found = scan_shopify(spec, body) if spec['kind'] == 'shopify' else scan_html(spec, body)
            result['merchants'].append({'merchant': spec['seller'], 'url': spec['url'], 'verified': len(found)})
            result['offers'].extend(found)
        except (HTTPError, URLError, ValueError, ET.ParseError, KeyError, TimeoutError, RuntimeError) as e:
            result['errors'].append({'url': spec['url'], 'error': str(e)[:180]})
    # Discovery RSS is review-only. An RSS item is *never* purchase-ready evidence.
    for url in FEEDS:
        try:
            result['discovery'].extend(feed_discovery(url, fetch(url)))
        except (HTTPError, URLError, ValueError, ET.ParseError, TimeoutError, RuntimeError) as e:
            result['errors'].append({'url': url, 'error': str(e)[:180]})
    return result


def main():
    output = Path(os.getenv('REPORT_FILE', 'report.json'))
    if dt.datetime.now(dt.timezone(dt.timedelta(hours=-4))).date() > END:
        print('Tracker window ended 2026-11-15. Exiting.'); return 0
    data = scan()
    data['offers'].sort(key=lambda d: (d['level'] != 'exceptional', d['before_tax'] or 9e9))
    for entry in data['offers']:
        if entry['level'] == 'exceptional':
            try:
                status = report_issue(entry)
                data['alerts'].append({'title': entry['title'], 'status': status})
            except Exception as exc:
                # Do not silently swallow failures that prevent alerts.
                data['alerts'].append({'title': entry['title'], 'status': 'FAILED', 'error': str(exc)})
                print(f'ERROR: could not alert: {exc}', file=sys.stderr)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for o in data['offers']:
        if o['level'] in ('exceptional', 'watch'):
            print(f"{o['level'].upper()}: {o['label']} {o['seller']} ${o['before_tax']:.2f} {o['url']}")
    print(f"Scanned {len(SHOPS)} direct merchant pages and {len(FEEDS)} RSS feeds; "
          f"{len(data['offers'])} stock-confirmed matched variants; "
          f"{len(data['discovery'])} unverified discoveries; {len(data['errors'])} failures")
    return 1 if any(a['status'] == 'FAILED' for a in data['alerts']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
