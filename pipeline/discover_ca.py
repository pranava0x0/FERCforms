"""Repeatable CPUC discovery; candidates stay outside the published corpus.

Discover official index links, cache capped PDFs, and save pages 1–3 for review.
Only an explicitly reviewed SourceSeed file can be ingested. Metadata-only
loading uses PyMuPDF page-by-page, avoiding full pdfplumber extraction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import shutil
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import fitz
import requests
from bs4 import BeautifulSoup

from pipeline import config
from pipeline.sources import load_seed, structure_seed

logger = logging.getLogger(__name__)
AUDITS = 'https://www.cpuc.ca.gov/about-cpuc/divisions/utility-audits-risk-and-compliance-division/utility-audits-branch/audit-reports-by-industry/audit-reports-energy-industry'
REFERENCES = 'https://www.publicadvocates.cpuc.ca.gov/press-room/reports-and-analyses'
RATE_CASES = 'https://www.cpuc.ca.gov/industries-and-topics/electrical-energy/electric-rates/general-rate-case/southern-california-edison-grc-proceedings'
INDEXES = {'audit': AUDITS, 'reference': REFERENCES, 'rate-case': RATE_CASES}
COLLECTIONS = {'audit': 'state_audit', 'reference': 'state_reference', 'rate-case': 'state_rate_case'}


def canonical(url: str) -> str:
    """Normalize URL identity without dropping identity-bearing queries."""
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), unquote(p.path).lower(), p.query, ''))


def assert_host(url: str) -> None:
    """Only CPUC-owned HTTPS endpoints, including every redirect destination."""
    p = urlsplit(url)
    host = p.hostname or ''
    if p.scheme != 'https' or not (host == 'cpuc.ca.gov' or host.endswith('.cpuc.ca.gov')):
        raise ValueError(f'Not a CPUC HTTPS source: {url}')


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.part')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(path)


def failure(url: str, exc: Exception) -> None:
    record = {'timestamp': datetime.now(timezone.utc).isoformat(), 'jurisdiction': 'CA',
              'status': 'failed', 'error': str(exc), 'url': url,
              'retryable': isinstance(exc, requests.RequestException),
              'next_steps': 'Inspect source and retry discovery; no report was published.'}
    with (config.DATA_DIR / 'ingest_log.jsonl').open('a') as stream:
        stream.write(json.dumps(record) + '\n')
    logger.error('%s: %s', url, exc)


def download(session: requests.Session, url: str, dest: Path, max_bytes: int) -> str:
    """Stream one response with a deadline; never cache partial/error content."""
    temporary = dest.with_suffix(dest.suffix + '.part')
    started = time.monotonic()
    try:
        for _ in range(6):
            assert_host(url)
            time.sleep(config.REQUEST_DELAY_SECONDS)
            with session.get(url, stream=True, timeout=(15, 40), allow_redirects=False) as response:
                response.raise_for_status()
                if response.is_redirect:
                    url = urljoin(url, response.headers['Location'])
                    continue
                if int(response.headers.get('Content-Length', '0')) > max_bytes:
                    raise ValueError('Source exceeds download byte limit')
                dest.parent.mkdir(parents=True, exist_ok=True)
                size = 0
                with temporary.open('wb') as stream:
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > max_bytes or time.monotonic() - started > 180:
                            raise ValueError('Source exceeds download byte/time limit')
                        stream.write(chunk)
                temporary.replace(dest)
                return url
        raise ValueError('Too many redirects')
    finally:
        temporary.unlink(missing_ok=True)


def links(html: str, base: str, kind: str, year: int | None = None) -> list[dict]:
    """Source-specific selectors; never construct document URLs or classify prose."""
    result = {}
    for anchor in BeautifulSoup(html, 'html.parser').select('a[href]'):
        url = urljoin(base, anchor['href'])
        label = anchor.get_text(' ', strip=True)
        path = urlsplit(url).path.lower()
        if kind == 'audit':
            keep = '/reports/energy/' in path and path.endswith('.pdf')
        elif kind == 'reference':
            keep = bool(re.fullmatch(r'\d{4} Q[1-4] Electric Rates Report', label))
        else:
            keep = path.endswith('.pdf') and bool(re.search(r'Application A\.|Track \d Decision|^D\.\d', label))
        if not keep or (year and str(year) not in url and str(year) not in label):
            continue
        assert_host(url)
        result[canonical(url)] = {'url': url, 'label': label, 'source_page_url': base}
    return list(result.values())


def discover(kind: str, output: Path, limit: int, year: int | None, match: str) -> int:
    session = requests.Session()
    session.headers['User-Agent'] = config.USER_AGENT
    cache = config.RAW_DIR / 'ca_discovery'
    cache.mkdir(parents=True, exist_ok=True)
    held = {canonical(s.pdf_url) for p in config.SEEDS_DIR.glob('*.json') for s in load_seed(p)}
    index = INDEXES[kind]
    index_path = cache / f'{kind}-index.html'
    resolved = download(session, index, index_path, 5_000_000)
    candidates = links(index_path.read_text(), resolved, kind, year)
    receipt = {'captured_at': date.today().isoformat(), 'kind': kind, 'index_url': index,
               'index_sha256': digest(index_path), 'scope': 'One index page; no pagination. Review captions before seeding.',
               'candidates': [], 'failures': [], 'already_held': 0}
    write_json(output, receipt)
    pattern = re.compile(match, re.I)
    for candidate in candidates:
        if not pattern.search(candidate['label']):
            continue
        url = candidate['url']
        try:
            if kind == 'reference':
                detail_path = cache / (hashlib.sha256(url.encode()).hexdigest() + '.html')
                download(session, url, detail_path, 5_000_000)
                soup = BeautifulSoup(detail_path.read_text(), 'html.parser')
                quarter = re.search(r'(\d{4}) Q([1-4])', candidate['label'])
                matches = [urljoin(url, a['href']) for a in soup.select('a[href]')
                           if urlsplit(a['href']).path.lower().endswith('.pdf')
                           and re.search(rf'q{quarter[2]}[-_ ]{quarter[1]}', a['href'], re.I)]
                if len(set(matches)) != 1:
                    raise ValueError('Expected exactly one matching quarterly report PDF')
                candidate['source_page_url'] = url
                candidate['detail_sha256'] = digest(detail_path)
                url = matches[0]
            if canonical(url) in held:
                receipt['already_held'] += 1
                continue
            key = hashlib.sha256(canonical(url).encode()).hexdigest()
            pdf = cache / f'{key}.pdf'
            cache_receipt = cache / f'{key}.json'
            cached = json.loads(cache_receipt.read_text()) if cache_receipt.exists() else {}
            if not pdf.exists() or digest(pdf) != cached.get('pdf_sha256'):
                final_url = download(session, url, pdf, 45_000_000)
                with pdf.open('rb') as stream:
                    if stream.read(5) != b'%PDF-':
                        pdf.unlink()
                        raise ValueError('Not a PDF')
                cached = {'pdf_sha256': digest(pdf), 'resolved_url': final_url,
                          'downloaded_at': datetime.now(timezone.utc).isoformat()}
                write_json(cache_receipt, cached)
            with fitz.open(pdf) as document:
                pages = [{'pdf_page': n + 1, 'text': document[n].get_text()} for n in range(min(3, len(document)))]
                if not pages or sum(len(p['text'].strip()) for p in pages) < 100:
                    raise ValueError('Caption requires OCR/manual source inspection')
                record = {**candidate, 'url': url, **cached, 'page_count': len(document),
                          'bytes': pdf.stat().st_size, 'caption_pages': pages}
            receipt['candidates'].append(record)
            write_json(output, receipt)
            logger.info('Candidate %d: %s (%d pages)', len(receipt['candidates']), candidate['label'], record['page_count'])
            if len(receipt['candidates']) >= limit:
                break
        except (requests.RequestException, ValueError, RuntimeError, OSError) as exc:
            failure(url, exc)
            receipt['failures'].append({'url': url, 'error': str(exc)})
        finally:
            write_json(output, receipt)
    logger.info('%d candidates, %d held, %d failures', len(receipt['candidates']), receipt['already_held'], len(receipt['failures']))
    return bool(receipt['failures'])


def ingest(seed_path: Path, receipt_path: Path) -> None:
    receipt = json.loads(receipt_path.read_text())
    candidates = {canonical(c['url']): c for c in receipt['candidates']}
    for seed in load_seed(seed_path):
        if seed.jurisdiction != 'CA' or seed.parse or not seed.fetch or seed.collection != COLLECTIONS[receipt['kind']]:
            raise ValueError('Only reviewed metadata-only CA seeds matching receipt kind are accepted')
        assert_host(seed.pdf_url)
        assert_host(seed.source_page_url)
        record = candidates[canonical(seed.pdf_url)]
        if canonical(seed.source_page_url) != canonical(record['source_page_url']):
            raise ValueError('Seed source page differs from discovery receipt')
        cache = config.RAW_DIR / 'ca_discovery' / (hashlib.sha256(canonical(seed.pdf_url).encode()).hexdigest() + '.pdf')
        if digest(cache) != record['pdf_sha256']:
            raise ValueError('Cached PDF differs from reviewed receipt')
        with fitz.open(cache) as pdf:
            if len(pdf) != record['page_count']:
                raise ValueError('Page count differs from reviewed receipt')
            scanned = [n + 1 for n in range(len(pdf)) if len(pdf[n].get_text().strip()) < config.MIN_TEXT_CHARS_PER_PAGE]
        report = structure_seed(seed, page_count=record['page_count'], scanned_pages=scanned)
        dest = config.PROCESSED_DIR / seed.id / 'report.json'
        payload = report.model_dump(mode='json')
        if dest.exists() and json.loads(dest.read_text()) != payload:
            raise ValueError(f'Refusing to overwrite changed existing report: {seed.id}')
        raw = config.RAW_DIR / f'{seed.id}.pdf'
        if raw.exists() and digest(raw) != record['pdf_sha256']:
            raise ValueError(f'Refusing to overwrite different cached source: {seed.id}')
        if not raw.exists():
            temporary = raw.with_suffix('.pdf.part')
            try:
                shutil.copyfile(cache, temporary)
                temporary.replace(raw)
            finally:
                temporary.unlink(missing_ok=True)
        write_json(dest, payload)
        logger.info('Ingested %s (%d pages; metadata-only)', seed.id, record['page_count'])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    discover_parser = sub.add_parser('discover')
    discover_parser.add_argument('--kind', choices=INDEXES, required=True)
    discover_parser.add_argument('--output', type=Path, required=True)
    discover_parser.add_argument('--limit', type=int, default=10)
    discover_parser.add_argument('--year', type=int)
    discover_parser.add_argument('--match', default='.')
    ingest_parser = sub.add_parser('ingest')
    ingest_parser.add_argument('--seed', type=Path, required=True)
    ingest_parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    try:
        if args.command == 'discover':
            if args.limit < 1:
                parser.error('--limit must be positive')
            raise SystemExit(discover(args.kind, args.output, args.limit, args.year, args.match))
        ingest(args.seed, args.receipt)
    except (requests.RequestException, ValueError, KeyError, OSError) as exc:
        failure(INDEXES.get(getattr(args, 'kind', ''), str(getattr(args, 'seed', ''))), exc)
        raise SystemExit(1) from exc


if __name__ == '__main__':
    main()
