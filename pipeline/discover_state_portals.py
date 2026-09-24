"""Bounded, repeatable GA docket, OR order and OH performance-audit discovery.

Candidates require caption review and a separate SourceSeed before ingestion.
No LLM, guessed PDF paths, full-corpus extraction, or automatic classification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit

import fitz
import requests
from bs4 import BeautifulSoup

from pipeline import config
from pipeline.discover_ca import canonical, digest, download, write_json
from pipeline.sources import load_seed, structure_seed

HOSTS = {
    'GA': {'psc.ga.gov', 'services.psc.ga.gov'},
    'OR': {'apps.puc.state.or.us', 'edocs.puc.state.or.us', 'www.oregon.gov'},
    'OH': {'ohioauditor.gov', 'www.ohioauditor.gov'},
}


def validate(state, url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.hostname not in HOSTS[state]:
        raise ValueError(f'Unexpected {state} source: {url}')


def document_links(html, base, state):
    rows = {}
    for a in BeautifulSoup(html, 'html.parser').select('a[href]'):
        url = urljoin(base, a['href'])
        label = a.get_text(' ', strip=True)
        if state == 'GA':
            keep = '/DownloadFile/' in url and label.lower().endswith('.pdf')
        elif state == 'OR':
            keep = 'orders.asp?OrderNumber=' in url or urlsplit(url).path.lower().endswith('.pdf')
        else:
            keep = '/auditsearch/Reports/' in url and urlsplit(url).path.lower().endswith('.pdf')
        if keep:
            validate(state, url)
            rows[canonical(url)] = {'url': url, 'label': label, 'source_page_url': base}
    return list(rows.values())


def fetch_index(session, state, url, receipt):
    key = hashlib.sha256(url.encode()).hexdigest()
    path = config.RAW_DIR / 'state_portals' / f'{key}.index'
    resolved = download(session, url, path, 5_000_000, lambda u: validate(state, u))
    receipt['indexes'].append({'url': url, 'resolved_url': resolved, 'sha256': digest(path)})
    raw = path.read_bytes()
    try:
        body = raw.decode("utf-8")
    except UnicodeDecodeError:
        body = raw.decode("windows-1252")
    return body, resolved


def record_failure(state, url, exc, receipt):
    entry = {'timestamp': datetime.now(timezone.utc).isoformat(), 'jurisdiction': state,
             'url': url, 'status': 'failed', 'error': str(exc),
             'retryable': isinstance(exc, requests.RequestException),
             'next_steps': 'Inspect recorded endpoint; retry explicitly. Nothing published.'}
    receipt['failures'].append(entry)
    with (config.DATA_DIR / 'ingest_log.jsonl').open('a') as out:
        out.write(json.dumps(entry) + '\n')


def discover(state, target, match, limit, output, search_text="Order"):
    session = requests.Session()
    session.headers['User-Agent'] = config.USER_AGENT
    receipt = {'jurisdiction': state, 'captured_at': datetime.now(timezone.utc).isoformat(),
               'target': target, 'match': match, 'search_text': search_text, 'scope': 'One index page; GA at most 50 matching filings. Not a completeness claim.',
               'indexes': [], 'candidates': [], 'failures': [], 'already_held': 0}
    held = {canonical(s.pdf_url) for p in config.SEEDS_DIR.glob('*.json') for s in load_seed(p)}
    pattern = re.compile(match, re.I)
    current = target
    try:
        if state == 'GA':
            if not target.isdigit():
                raise ValueError('GA target must be a docket number')
            # Endpoint and field names observed in the public docket.v2.js client.
            current = 'https://psc.ga.gov/search/service-facts-docket/?' + urlencode({
                'docketId': target, 'sortDirection': 'DESC', 'sortColumn': 'Filed',
                'searchText': search_text, 'pageSize': 50, 'pageNumber': 1})
            body, _ = fetch_index(session, state, current, receipt)
            data = json.loads(body)
            receipt['results_count'] = data['resultsCount']
            receipt['truncated'] = data['resultsCount'] > len(data['resultsItems'])
            pages = [('https://psc.ga.gov/search/facts-document/?documentId=' + str(r['documentId']), r)
                     for r in data['resultsItems'] if pattern.search(r['description'])]
        else:
            pages = [(target, None)]
        if not pages:
            raise ValueError('No matching filing rows; narrow query/source needs review')
        for page, metadata in pages:
            current = page
            body, resolved = fetch_index(session, state, page, receipt)
            rows = document_links(body, resolved, state)
            if not rows:
                raise ValueError(f'No document links on {page}; inspect layout or scanned attachments')
            for row in rows:
                if state != 'GA' and not pattern.search(row['label'] + ' ' + row['url']):
                    continue
                current = row['url']
                if canonical(current) in held:
                    receipt['already_held'] += 1
                    continue
                key = hashlib.sha256(canonical(current).encode()).hexdigest()
                pdf = config.RAW_DIR / 'state_portals' / f'{key}.pdf'
                cached_file = pdf.with_suffix('.json')
                cached = json.loads(cached_file.read_text()) if cached_file.exists() else {}
                try:
                    if not pdf.exists() or digest(pdf) != cached.get('pdf_sha256'):
                        final = download(session, current, pdf, 45_000_000, lambda u: validate(state, u))
                        with pdf.open('rb') as stream:
                            if stream.read(5) != b'%PDF-':
                                pdf.unlink()
                                raise ValueError('Not a PDF')
                        cached = {'pdf_sha256': digest(pdf), 'resolved_url': final,
                                  'downloaded_at': datetime.now(timezone.utc).isoformat()}
                        write_json(cached_file, cached)
                    if canonical(cached['resolved_url']) in held:
                        receipt['already_held'] += 1
                        continue
                    with fitz.open(pdf) as doc:
                        captions = [{'pdf_page': n+1, 'text': doc[n].get_text()} for n in range(min(3, len(doc)))]
                        record = {**row, **cached, 'page_count': len(doc), 'bytes': pdf.stat().st_size,
                                  'cache_path': str(pdf.relative_to(config.DATA_DIR.parent)),
                                  'caption_pages': captions, 'index_metadata': metadata,
                                  'needs_visual_review': sum(len(p['text'].strip()) for p in captions) < 100}
                    receipt['candidates'].append(record)
                    write_json(output, receipt)
                    if len(receipt['candidates']) >= limit:
                        return receipt
                except (requests.RequestException, ValueError, RuntimeError, OSError) as exc:
                    record_failure(state, current, exc, receipt)
                finally:
                    write_json(output, receipt)
    except (requests.RequestException, ValueError, KeyError, OSError) as exc:
        record_failure(state, current, exc, receipt)
    finally:
        write_json(output, receipt)
    return receipt


def ingest(seed_path, receipt_path):
    """Require exact reviewed metadata, source identity and cached bytes; never overwrite drift."""
    paths = receipt_path if isinstance(receipt_path, list) else [receipt_path]
    receipts = [json.loads(p.read_text()) for p in paths]
    states = {r.get('jurisdiction', r.get('state')) for r in receipts}
    if len(states) != 1:
        raise ValueError('Ingest receipts must belong to one jurisdiction')
    receipt = {'jurisdiction': states.pop(), 'candidates': [c for r in receipts for c in r['candidates']]}
    records = {canonical(r['url']): r for r in receipt['candidates']}
    for seed in load_seed(seed_path):
        if seed.parse or not seed.fetch:
            raise ValueError('Only fetched metadata-only seeds supported')
        record = records[canonical(seed.pdf_url)]
        reviewed = record.get('reviewed_metadata')
        if reviewed != seed.model_dump(mode='json'):
            raise ValueError(f'Seed differs from reviewed metadata: {seed.id}')
        if seed.jurisdiction != receipt['jurisdiction']:
            raise ValueError('Seed jurisdiction differs from receipt')
        if canonical(seed.source_page_url) != canonical(record['source_page_url']):
            raise ValueError('Seed source page differs from receipt')
        cache = (config.DATA_DIR.parent / record['cache_path']).resolve()
        if config.RAW_DIR.resolve() not in cache.parents or digest(cache) != record['pdf_sha256']:
            raise ValueError('Cached source path/hash differs from receipt')
        with fitz.open(cache) as doc:
            if len(doc) != record['page_count']:
                raise ValueError('Page count differs from receipt')
            scanned = [n+1 for n in range(len(doc)) if len(doc[n].get_text().strip()) < config.MIN_TEXT_CHARS_PER_PAGE]
        report = structure_seed(seed, page_count=record['page_count'], scanned_pages=scanned).model_dump(mode='json')
        dest = config.PROCESSED_DIR / seed.id / 'report.json'
        raw = config.RAW_DIR / f'{seed.id}.pdf'
        if dest.exists() and json.loads(dest.read_text()) != report:
            raise ValueError(f'Refusing changed report: {seed.id}')
        if raw.exists() and digest(raw) != record['pdf_sha256']:
            raise ValueError(f'Refusing changed PDF: {seed.id}')
        if not raw.exists():
            part = raw.with_suffix('.pdf.part')
            try:
                shutil.copyfile(cache, part)
                part.replace(raw)
            finally:
                part.unlink(missing_ok=True)
        write_json(dest, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    d = sub.add_parser('discover')
    d.add_argument('--state', choices=HOSTS, required=True)
    d.add_argument('--target', required=True, help='GA docket number; OR docket URL; OH performance-audit detail URL')
    d.add_argument('--match', default='Order', help='Regex over GA descriptions or OR/OH link labels/URLs')
    d.add_argument('--search-text', default='Order', help='GA server-side search; first 50 results only')
    d.add_argument('--limit', type=int, default=3)
    d.add_argument('--output', type=Path, required=True)
    i = sub.add_parser('ingest')
    i.add_argument('--seed', type=Path, required=True)
    i.add_argument('--receipt', type=Path, nargs='+', required=True)
    args = parser.parse_args()
    if args.command == 'ingest':
        ingest(args.seed, args.receipt)
    else:
        if not 1 <= args.limit <= 20:
            parser.error('limit must be 1–20')
        result = discover(args.state, args.target, args.match, args.limit, args.output, args.search_text)
        print(f"{len(result['candidates'])} candidates; {result['already_held']} held; {len(result['failures'])} failures")
        raise SystemExit(bool(result['failures']))


if __name__ == '__main__':
    main()
