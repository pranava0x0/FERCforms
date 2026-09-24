"""Bounded official-document discovery for VA, TX, PA and NY.

Discovery receipts are review material, never source seeds. Each receipt records
an observed link, PDF hash and pages 1-3. Review caption and docket before
copying a candidate into a metadata-only seed.

Examples:
  python -m pipeline.discover_eastern_states TX --docket 56211 --match '^(ORDER|Stipulation)' --limit 3 --output data/sources/eastern-tx.json
  python -m pipeline.discover_eastern_states NY --docket 24-E-0322 --match 'Order Adopting' --limit 2 --output data/sources/eastern-ny.json
  python -m pipeline.discover_eastern_states PA --index-url https://www.puc.pa.gov/... --match 'Final Order' --limit 2 --output data/sources/eastern-pa.json
  python -m pipeline.discover_eastern_states VA --docket PUR-2024-00137 --match 'Final Order' --limit 2 --output data/sources/eastern-va.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit, urlunsplit

import fitz
import requests
from bs4 import BeautifulSoup

from pipeline import config
from pipeline.discover_ca import digest, download
from pipeline.sources import is_official_gov, load_seed

logger = logging.getLogger(__name__)
HOSTS = {
    'VA': ('scc.virginia.gov',),
    'TX': ('interchange.puc.texas.gov',),
    'PA': ('puc.pa.gov',),
    'NY': ('dps.ny.gov',),
}
MAX_BYTES = 45_000_000


def canonical(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), unquote(p.path).lower(), p.query, ''))


def check_url(state: str, url: str) -> None:
    p = urlsplit(url)
    host = p.hostname or ''
    if p.scheme != 'https' or not is_official_gov(url) or not any(host == h or host.endswith('.' + h) for h in HOSTS[state]):
        raise ValueError(f'Not an official {state} HTTPS endpoint: {url}')


def save(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.part')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def fetch(session: requests.Session, state: str, url: str, path: Path, cap: int = MAX_BYTES) -> str:
    """Use the shared 180-second bounded downloader with state-host checks."""
    return download(session, url, path, cap, validate_url=lambda target: check_url(state, target))


def cached_pdf(session: requests.Session, state: str, url: str, path: Path) -> dict:
    """Trust cached bytes only when their recorded digest still matches."""
    sidecar = path.with_suffix('.json')
    prior = json.loads(sidecar.read_text()) if sidecar.exists() else {}
    if path.exists() and prior.get('pdf_sha256') == digest(path):
        with path.open('rb') as stream:
            if stream.read(5) == b'%PDF-':
                return prior
    resolved = fetch(session, state, url, path)
    with path.open('rb') as stream:
        if stream.read(5) != b'%PDF-':
            path.unlink(missing_ok=True)
            raise ValueError('Response is not a PDF')
    metadata = {'pdf_sha256': digest(path), 'resolved_url': resolved,
                'downloaded_at': datetime.now(timezone.utc).isoformat()}
    save(sidecar, metadata)
    return metadata


def log_failure(state: str, url: str, exc: Exception) -> None:
    entry = {'timestamp': datetime.now(timezone.utc).isoformat(), 'jurisdiction': state,
             'status': 'failed', 'error': str(exc), 'url': url,
             'retryable': isinstance(exc, requests.RequestException),
             'next_steps': 'Inspect the source and retry; no candidate was published.'}
    with (config.DATA_DIR / 'ingest_log.jsonl').open('a') as stream:
        stream.write(json.dumps(entry) + '\n')


def html_links(state: str, html: str, index_url: str) -> list[dict]:
    """Harvest only observed links. TX uses filing and item detail pages."""
    found: dict[str, dict] = {}
    soup = BeautifulSoup(html, 'html.parser')
    if state == 'TX':
        for row in soup.select('tr'):
            anchor = row.select_one('a[href*="/search/documents/"]')
            if anchor:
                url = urljoin(index_url, anchor['href'])
                check_url(state, url)
                found[canonical(url)] = {'detail_url': url, 'label': row.get_text(' ', strip=True), 'index_url': index_url}
    else:
        for anchor in soup.select('a[href]'):
            url = urljoin(index_url, anchor['href'])
            path = urlsplit(url).path.lower()
            label = anchor.get_text(' ', strip=True)
            if state == 'NY':
                label = parse_qs(urlsplit(url).query).get('docTitle', [label])[0]
                match = re.search(r'[?&]id=(%7b[0-9a-f-]+%7d)', url, re.I)
                if not match or '/viewdoc/find' not in path and '/downloaddoc/find' not in path:
                    continue
                # GUID observed in live anchor; this canonical official ViewDoc route is documented by DPS.
                url = 'https://documents.dps.ny.gov/public/Common/ViewDoc.aspx?DocRefId=' + match.group(1)
            elif not path.endswith('.pdf') and not (state == 'VA' and '/docketsearch/docs/' in path):
                continue
            check_url(state, url)
            found[canonical(url)] = {'url': url, 'label': label, 'index_url': index_url}
    return list(found.values())


def index_for(state: str, docket: str, session: requests.Session, cache: Path) -> tuple[str, list[dict]]:
    if state == 'TX':
        url = 'https://interchange.puc.texas.gov/search/filings/?ControlNumber=' + quote(docket)
    elif state == 'NY':
        url = 'https://documents.dps.ny.gov/search/Home/DocumentSearch2/?searchCriteria=' + quote(docket)
    elif state == 'VA':
        base = 'https://www.scc.virginia.gov/DocketSearchAPI/breeze/'
        cases_url = base + "CASES_ESTABDATE/GetCasesEstDate?$filter=Case_Number%20eq%20%27" + quote(docket) + "%27&$select=MATTER_NO,Case_Number"
        cases_path = cache / 'cases.json'
        fetch(session, state, cases_url, cases_path, 2_000_000)
        cases = json.loads(cases_path.read_text())
        if len(cases) != 1 or cases[0].get('Case_Number') != docket:
            raise ValueError('VA docket not uniquely resolved')
        number = int(cases[0]['MATTER_NO'])
        url = base + 'CaseDetails/GetDocuments?$filter=MATTER_NO%20eq%20' + str(number) + '&$select=Document_Name,DocID,FileName'
        path = cache / 'documents.json'
        fetch(session, state, url, path, 10_000_000)
        documents = json.loads(path.read_text())
        rows = []
        for doc in documents:
            name = doc.get('FileName')
            if name and name.lower().endswith('.pdf'):
                pdf_url = 'https://www.scc.virginia.gov/docketsearch/DOCS/' + quote(name, safe='!.')
                rows.append({'url': pdf_url, 'label': doc.get('Document_Name', ''), 'index_url': url, 'document_id': doc.get('DocID')})
        return url, rows
    else:
        raise ValueError('PA requires --index-url')
    path = cache / 'index.html'
    fetch(session, state, url, path, 12_000_000)
    return url, html_links(state, path.read_text(errors='replace'), url)


def discover(state: str, output: Path, *, docket: str | None, index_url: str | None,
             document_url: str | None = None,
             match: str, limit: int) -> dict:
    if limit < 1 or limit > 20:
        raise ValueError('Limit must be 1..20')
    session = requests.Session()
    session.headers['User-Agent'] = config.USER_AGENT
    cache = config.RAW_DIR / 'eastern_discovery' / state.lower() / hashlib.sha256((index_url or docket or document_url or '').encode()).hexdigest()[:16]
    cache.mkdir(parents=True, exist_ok=True)
    held = {canonical(seed.pdf_url) for path in config.SEEDS_DIR.glob('*.json') for seed in load_seed(path)}
    if document_url:
        check_url(state, document_url)
        rows = [{'url': document_url, 'label': document_url, 'index_url': document_url}]
        source = document_url
    elif index_url:
        check_url(state, index_url)
        index_path = cache / 'index.html'
        fetch(session, state, index_url, index_path, 12_000_000)
        rows = html_links(state, index_path.read_text(errors='replace'), index_url)
        source = index_url
    elif docket:
        source, rows = index_for(state, docket, session, cache)
    else:
        raise ValueError('Give --docket, --index-url or --document-url')
    index_file = cache / ('documents.json' if state == 'VA' and docket else 'index.html')
    receipt = {'captured_at': date.today().isoformat(), 'state': state, 'docket_query': docket,
               'index_url': source, 'scope': ('First 50 relevance-ranked search results; sibling cases possible; coverage unknown' if state == 'NY' else 'One observed index; review captions before seeding'),
               'rows_seen': len(rows), 'matched_rows': 0,
               'candidates': [], 'failures': [], 'already_held': 0}
    if index_file.exists() and not document_url:
        receipt['index_sha256'] = digest(index_file)
    if state == 'VA' and docket:
        receipt['case_index_sha256'] = digest(cache / 'cases.json')
    save(output, receipt)
    pattern = re.compile(match, re.I)
    for row in rows:
        if not pattern.search(row['label']):
            continue
        receipt['matched_rows'] += 1
        try:
            if state == 'TX':
                detail = row['detail_url']
                detail_path = cache / (hashlib.sha256(detail.encode()).hexdigest()[:16] + '.html')
                fetch(session, state, detail, detail_path, 3_000_000)
                row['detail_sha256'] = digest(detail_path)
                anchors = BeautifulSoup(detail_path.read_text(errors='replace'), 'html.parser').select('a[href]')
                urls = [urljoin(detail, a['href']) for a in anchors if '/Documents/' in a['href'] and a['href'].lower().endswith('.pdf')]
                if len(set(urls)) != 1:
                    raise ValueError(f'Expected one PDF on TX item page, found {len(set(urls))}')
                row['url'] = urls[0]
            url = row['url']
            check_url(state, url)
            if canonical(url) in held:
                receipt['already_held'] += 1
                continue
            key = hashlib.sha256(canonical(url).encode()).hexdigest()
            pdf = cache / (key + '.pdf')
            metadata = cached_pdf(session, state, url, pdf)
            with fitz.open(pdf) as document:
                pages = [{'pdf_page': n+1, 'text': document[n].get_text()} for n in range(min(3, len(document)))]
                if sum(len(p['text'].strip()) for p in pages) < 100:
                    raise ValueError('Pages 1-3 need OCR/manual inspection')
                count = len(document)
            receipt['candidates'].append({**row, 'source_page_url': row.get('detail_url', row['index_url']),
                                          'cache_path': str(pdf.relative_to(config.ROOT)),
                                          **metadata,
                                          'page_count': count, 'bytes': pdf.stat().st_size,
                                          'caption_pages': pages})
            save(output, receipt)
            if len(receipt['candidates']) >= limit:
                break
        except (requests.RequestException, ValueError, RuntimeError, OSError) as exc:
            receipt['failures'].append({'url': row.get('url', row.get('detail_url')), 'error': str(exc)})
            save(output, receipt)
            log_failure(state, row.get('url', row.get('detail_url', source)), exc)
            logger.warning('%s: %s', row.get('label'), exc)
    save(output, receipt)
    if receipt['matched_rows'] == 0:
        logger.warning('No matching links in sampled index; coverage is unknown')
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state', choices=HOSTS)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--docket')
    group.add_argument('--index-url')
    group.add_argument('--document-url', help='Direct official PDF link observed in a regulator page or search result')
    parser.add_argument('--match', default='.')
    parser.add_argument('--limit', type=int, default=3)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    try:
        receipt = discover(args.state, args.output, docket=args.docket, index_url=args.index_url,
                           document_url=args.document_url, match=args.match, limit=args.limit)
    except (requests.RequestException, ValueError, RuntimeError, OSError) as exc:
        log_failure(args.state, args.index_url or args.document_url or args.docket, exc)
        logger.error('Discovery failed: %s', exc)
        raise SystemExit(1) from exc
    logger.info('%d candidates; %d held; %d failures', len(receipt['candidates']),
                receipt['already_held'], len(receipt['failures']))
    if receipt['failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
