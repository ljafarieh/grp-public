"""
News ingestion: fetches recent headlines per ticker and stores them in a
local SQLite database (cache/news.db).

Primary source: Yahoo Finance RSS feeds (free, no key required).
Optional upgrade: NewsAPI.org (free tier, requires NEWSAPI_KEY in .env).

Switch by setting news_source in config/universe.yaml:
  news_source: rss       ← default
  news_source: newsapi   ← requires NEWSAPI_KEY in .env
"""

from __future__ import annotations

import logging
import os
import sqlite3
import ssl
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
NEWS_DB_PATH = PROJECT_ROOT / "cache" / "news.db"

# SSL context using certifi bundle (fixes macOS Python missing system certs)
def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    return ctx


# RSS request headers — Yahoo will 403 a bare urllib user-agent
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


# ---------------------------------------------------------------------------
# DB schema
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    NEWS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(NEWS_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS headlines (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT NOT NULL,
            published   TEXT NOT NULL,   -- ISO-8601 date string
            title       TEXT NOT NULL,
            source      TEXT,
            url         TEXT,
            fetched_at  TEXT NOT NULL,
            UNIQUE(ticker, published, title)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker_date ON headlines(ticker, published)")
    conn.commit()
    return conn


def _upsert_headlines(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Insert rows, ignore duplicates. Returns count of newly inserted rows."""
    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO headlines
                   (ticker, published, title, source, url, fetched_at)
                   VALUES (:ticker, :published, :title, :source, :url, :fetched_at)""",
                row,
            )
            if conn.total_changes > 0:
                inserted += 1
        except sqlite3.Error as exc:
            logger.warning("DB insert failed for %s: %s", row.get("ticker"), exc)
    conn.commit()
    return inserted


# ---------------------------------------------------------------------------
# RSS adapter (primary / free)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# yfinance news adapter (primary — reuses same session as price data)
# ---------------------------------------------------------------------------

def _fetch_yfinance_news(ticker: str, max_items: int = 10) -> list[dict]:
    """
    Use yfinance Ticker.news to pull recent headlines. This shares the same
    Yahoo Finance session as our price data — no separate rate-limit bucket.
    Returns at most max_items headline dicts.
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        raw_news = t.news or []
    except Exception as exc:
        logger.warning("yfinance news failed for %s: %s", ticker, exc)
        return []

    now = datetime.now(timezone.utc).isoformat()
    items = []
    for article in raw_news[:max_items]:
        # yfinance >=0.2.50 nests everything under article["content"]
        content = article.get("content") or article

        title = (content.get("title") or "").strip()
        if not title:
            continue

        # pubDate is ISO-8601 string in new schema; Unix ts in old schema
        pub_raw = content.get("pubDate") or content.get("displayTime") or ""
        pub_ts_old = article.get("providerPublishTime") or article.get("publishTime")
        try:
            if pub_raw:
                pub_str = datetime.fromisoformat(pub_raw.replace("Z", "+00:00")).date().isoformat()
            elif pub_ts_old:
                pub_str = datetime.fromtimestamp(int(pub_ts_old), tz=timezone.utc).date().isoformat()
            else:
                pub_str = date.today().isoformat()
        except Exception:
            pub_str = date.today().isoformat()

        # URL: new schema has canonicalUrl or clickThroughUrl sub-dicts
        canonical = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
        link = canonical.get("url") if isinstance(canonical, dict) else ""
        link = link or article.get("link", "")

        provider = content.get("provider") or {}
        publisher = (
            provider.get("displayName") if isinstance(provider, dict) else None
        ) or article.get("publisher", "yahoo_finance")

        items.append({
            "ticker": ticker.upper(),
            "published": pub_str,
            "title": title,
            "source": publisher,
            "url": link,
            "fetched_at": now,
        })

    return items


# ---------------------------------------------------------------------------
# Yahoo Finance RSS adapter (fallback)
# ---------------------------------------------------------------------------

_YAHOO_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"


def _fetch_rss(ticker: str, max_items: int = 10) -> list[dict]:
    url = _YAHOO_RSS_URL.format(ticker=quote_plus(ticker))
    try:
        req = Request(url, headers=_HEADERS)
        with urlopen(req, timeout=10, context=_ssl_context()) as resp:
            body = resp.read()
    except Exception as exc:
        logger.warning("RSS fetch failed for %s: %s", ticker, exc)
        return []

    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        logger.warning("RSS parse failed for %s: %s", ticker, exc)
        return []

    now = datetime.now(timezone.utc).isoformat()
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        pub_raw = (item.findtext("pubDate") or "").strip()
        link = (item.findtext("link") or "").strip()

        if not title:
            continue

        # Parse RFC-2822 date → ISO date string; fall back to today
        try:
            from email.utils import parsedate_to_datetime
            pub_dt = parsedate_to_datetime(pub_raw)
            pub_str = pub_dt.date().isoformat()
        except Exception:
            pub_str = date.today().isoformat()

        items.append({
            "ticker": ticker.upper(),
            "published": pub_str,
            "title": title,
            "source": "yahoo_rss",
            "url": link,
            "fetched_at": now,
        })

        if len(items) >= max_items:
            break

    return items


# ---------------------------------------------------------------------------
# NewsAPI adapter (optional upgrade — requires NEWSAPI_KEY in .env)
# ---------------------------------------------------------------------------

def _fetch_newsapi(
    ticker: str,
    lookback_days: int = 3,
    max_items: int = 10,
) -> list[dict]:
    api_key = os.getenv("NEWSAPI_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "NEWSAPI_KEY not set in .env. Either add the key or switch "
            "news_source to 'rss' in config/universe.yaml."
        )

    from_date = (date.today() - timedelta(days=lookback_days)).isoformat()
    query = quote_plus(ticker)
    url = (
        f"https://newsapi.org/v2/everything"
        f"?q={query}&from={from_date}&sortBy=publishedAt"
        f"&language=en&pageSize={max_items}&apiKey={api_key}"
    )

    try:
        req = Request(url, headers={"User-Agent": "pipeline-research/1.0"})
        with urlopen(req, timeout=10) as resp:
            import json
            data = json.loads(resp.read())
    except Exception as exc:
        logger.warning("NewsAPI fetch failed for %s: %s", ticker, exc)
        return []

    now = datetime.now(timezone.utc).isoformat()
    items = []
    for article in data.get("articles", []):
        pub_raw = article.get("publishedAt", "")
        try:
            pub_str = datetime.fromisoformat(pub_raw.replace("Z", "+00:00")).date().isoformat()
        except Exception:
            pub_str = date.today().isoformat()

        items.append({
            "ticker": ticker.upper(),
            "published": pub_str,
            "title": (article.get("title") or "").strip(),
            "source": (article.get("source", {}).get("name") or "newsapi"),
            "url": article.get("url", ""),
            "fetched_at": now,
        })
    return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_news_for_ticker(
    ticker: str,
    source: str = "yfinance",
    lookback_days: int = 3,
    max_items: int = 10,
) -> list[dict]:
    """
    Fetch headlines for one ticker. Returns list of headline dicts.
    Sources: "yfinance" (default), "rss" (fallback), "newsapi" (paid key).
    """
    if source == "newsapi":
        return _fetch_newsapi(ticker, lookback_days, max_items)
    if source == "rss":
        return _fetch_rss(ticker, max_items)
    # Default: yfinance, with RSS fallback
    results = _fetch_yfinance_news(ticker, max_items)
    if not results:
        logger.debug("%s: yfinance news empty, trying RSS fallback", ticker)
        results = _fetch_rss(ticker, max_items)
    return results


def ingest_news(
    tickers: list[str],
    source: str = "rss",
    lookback_days: int = 3,
    max_items: int = 10,
    sleep_between: float = 0.5,
) -> dict[str, int]:
    """
    Fetch and store news for all tickers. Returns dict of ticker → new rows inserted.
    sleep_between: seconds to pause between requests (be polite to free APIs).
    """
    conn = _get_conn()
    results = {}
    for ticker in tickers:
        rows = fetch_news_for_ticker(ticker, source, lookback_days, max_items)
        new_count = _upsert_headlines(conn, rows)
        results[ticker] = new_count
        logger.debug("  %-8s  %d headlines (%d new)", ticker, len(rows), new_count)
        if sleep_between > 0:
            time.sleep(sleep_between)
    conn.close()
    return results


def get_headlines(
    ticker: str,
    for_date: date,
    lookback_days: int = 3,
) -> list[dict]:
    """
    Retrieve stored headlines for ticker within lookback_days before for_date.
    Used by the attribution module to explain price moves.
    """
    start = (for_date - timedelta(days=lookback_days)).isoformat()
    end = for_date.isoformat()
    conn = _get_conn()
    rows = conn.execute(
        """SELECT published, title, source, url
           FROM headlines
           WHERE ticker = ? AND published >= ? AND published <= ?
           ORDER BY published DESC""",
        (ticker.upper(), start, end),
    ).fetchall()
    conn.close()
    return [
        {"published": r[0], "title": r[1], "source": r[2], "url": r[3]}
        for r in rows
    ]
