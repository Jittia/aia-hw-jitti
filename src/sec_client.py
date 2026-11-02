"""Shared SEC EDGAR HTTP client: User-Agent from .env, 10 req/s throttle, retry, gzip cache.

SEC fair-access rules: https://www.sec.gov/os/accessing-edgar-data
(declare a User-Agent with name + email, stay at or below 10 requests per second).
"""
from __future__ import annotations

import gzip
import json
import os
import threading
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_PRIVATE = ROOT / "data" / "private"
DATA_CACHE = ROOT / "data" / "cache"

MIN_INTERVAL_S = 0.11  # just under 10 requests/second
MAX_RETRIES = 5


def load_env(path: Path = ROOT / ".env") -> dict[str, str]:
    """Minimal KEY=VALUE reader so no extra dependency is needed."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


class SecClient:
    def __init__(self) -> None:
        user_agent = load_env().get("SEC_USER_AGENT")
        if not user_agent or "@" not in user_agent:
            raise SystemExit(
                "Missing SEC_USER_AGENT in .env (format: SEC_USER_AGENT=Your Name your@email.com). "
                "See .env.example."
            )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
        self._last_request = 0.0
        self._lock = threading.Lock()
        self.requests_made = 0

    def _throttle(self) -> None:
        # Thread-safe: worker threads reserve evenly spaced send slots, so the total stays <= 10/s.
        with self._lock:
            slot = max(time.monotonic(), self._last_request + MIN_INTERVAL_S)
            self._last_request = slot
        wait = slot - time.monotonic()
        if wait > 0:
            time.sleep(wait)

    def get_json(self, url: str) -> dict | None:
        """GET a JSON document. Returns None on 404. Retries 429/5xx/network errors with backoff."""
        for attempt in range(MAX_RETRIES):
            self._throttle()
            try:
                resp = self.session.get(url, timeout=30)
            except requests.RequestException:
                time.sleep(2 ** attempt)
                continue
            self.requests_made += 1
            if resp.status_code == 404:
                return None
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2 ** attempt * 2)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"Failed after {MAX_RETRIES} attempts: {url}")

    def get_json_cached(self, url: str, cache_file: Path, refresh: bool = False) -> dict | None:
        """Fetch once and keep a gzip copy; later calls read the cache (makes runs resumable).
        A 404 is cached as {"_missing": true} so it is not requested again."""
        if cache_file.exists() and not refresh:
            return read_cache(cache_file)
        data = self.get_json(url)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_file.with_suffix(f"{cache_file.suffix}.{os.getpid()}-{threading.get_ident()}.tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(data if data is not None else {"_missing": True}, f)
        tmp.replace(cache_file)
        return data


def read_cache(cache_file: Path) -> dict | None:
    with gzip.open(cache_file, "rt", encoding="utf-8") as f:
        data = json.load(f)
    return None if data.get("_missing") else data


def cik10(cik: int | str) -> str:
    return str(int(cik)).zfill(10)
