"""SEC transport: sequential pacing, retries, exact-byte cache and URL checks."""
from __future__ import annotations
import hashlib, json, re, threading, time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

class SECError(RuntimeError):
    pass

class SECClient:
    def __init__(self, identity: str, cache_dir='.sec_cache', timeout=40, interval=.25):
        if not re.search(r'[^\s@]+@[^\s@]+\.[^\s@]+', identity or '') or re.search(r'@example\.(com|org|net)', identity):
            raise ValueError('Provide your name/application and real email using --identity or SEC_USER_AGENT.')
        self.identity, self.timeout = identity, timeout
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.interval, self.last = max(.15, interval), 0.0
        self.lock = threading.Lock()

    @staticmethod
    def validate_url(url):
        u = urlparse(url)
        if u.scheme != 'https' or u.hostname not in {'www.sec.gov', 'data.sec.gov'} or u.username or u.password or u.port:
            raise ValueError('Only canonical HTTPS SEC URLs are accepted.')
        return url

    def get_bytes(self, url: str, ttl=3600):
        self.validate_url(url)
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.cache_dir / (key + '.bin')
        if path.exists() and (ttl is None or time.time()-path.stat().st_mtime < ttl):
            return path.read_bytes()
        for attempt in range(5):
            with self.lock:
                wait = self.interval-(time.monotonic()-self.last)
                if wait > 0: time.sleep(wait)
                self.last = time.monotonic()
            request = Request(url, headers={'User-Agent': self.identity, 'Accept': '*/*'})
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    data = response.read()
                temp = path.with_suffix('.tmp')
                temp.write_bytes(data)
                temp.replace(path)
                return data
            except HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504}:
                    raise SECError(f'SEC HTTP {exc.code}: {url}') from exc
                delay = exc.headers.get('Retry-After', '')
                time.sleep(min(30, float(delay) if delay.isdigit() else 2**attempt))
            except (URLError, TimeoutError, OSError) as exc:
                if attempt == 4: raise SECError(f'SEC transport failed: {url}: {exc}') from exc
                time.sleep(2**attempt)
        raise SECError(f'SEC remained unavailable after retries: {url}')

    def get_json(self, url, ttl=3600):
        return json.loads(self.get_bytes(url, ttl))

    def resolve(self, symbol):
        value = str(symbol).strip().upper()
        if value.isdigit() and 0 < int(value) < 10**10:
            return str(int(value)).zfill(10)
        mapping = self.get_json('https://www.sec.gov/files/company_tickers.json', 86400)
        for row in mapping.values():
            if row['ticker'].replace('.', '-') == value.replace('.', '-'):
                return str(row['cik_str']).zfill(10)
        raise SECError(f'Ticker not found: {symbol}. You can pass a CIK instead.')
