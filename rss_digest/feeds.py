"""Fetch RSS/Atom feeds and turn their entries into plain-text articles."""

from __future__ import annotations

import functools
import logging
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import certifi
import feedparser

logger = logging.getLogger(__name__)

USER_AGENT = "rss-digest/0.1"
TIMEOUT_SECONDS = 15
MAX_FEED_BYTES = 5 * 1024 * 1024

# Tags whose end should be treated as a break between words/sentences.
_BLOCK_TAGS = {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "blockquote"}
# Code blocks don't summarize well, so they are dropped along with scripts and styles.
_SKIP_TAGS = {"script", "style", "pre"}


@dataclass
class Article:
    source: str
    title: str
    link: str
    published: datetime | None
    text: str


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        # Text inside skipped tags is held here, so an unclosed <pre> doesn't
        # swallow the rest of the article.
        self._skipped: list[str] = []
        self._skip_stack: list[str] = []

    def _out(self) -> list[str]:
        return self._skipped if self._skip_stack else self.parts

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_stack.append(tag)
        elif tag in _BLOCK_TAGS:
            self._out().append("\n")

    def handle_endtag(self, tag):
        if tag in self._skip_stack:
            while self._skip_stack.pop() != tag:
                pass
            if not self._skip_stack:
                self._skipped.clear()
        elif tag in _BLOCK_TAGS:
            self._out().append("\n")

    def handle_data(self, data):
        self._out().append(data)

    def close(self):
        super().close()
        # Browsers also treat an unclosed <script>/<style> as running to the end,
        # but an unclosed <pre> is usually just sloppy markup worth keeping.
        if self._skip_stack and not {"script", "style"} & set(self._skip_stack):
            self.parts.extend(self._skipped)


def html_to_text(html: str) -> str:
    """Strip tags and entities, collapse whitespace while keeping paragraph breaks."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)


def load_feed_urls(path: str | Path) -> list[str]:
    """Read one URL per line, ignoring blank lines and `#` comments."""
    urls = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            urls.append(line)
    return urls


@functools.cache
def _ssl_context() -> ssl.SSLContext:
    # Use certifi's CA bundle so HTTPS works even where the system Python has no
    # certificates configured (common with python.org installers on macOS).
    # Built on first download, so importing the package never touches the file.
    return ssl.create_default_context(cafile=certifi.where())


def download(url: str) -> bytes:
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        raise ValueError(f"only http(s) feed URLs are supported: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=_ssl_context()) as response:
        data = response.read(MAX_FEED_BYTES + 1)
    if len(data) > MAX_FEED_BYTES:
        raise ValueError(f"feed is larger than {MAX_FEED_BYTES // (1024 * 1024)} MB")
    return data


def parse_feed(raw: bytes | str, limit: int | None = None) -> list[Article]:
    """Parse feed content (RSS or Atom) into articles, newest entries first as given by the feed."""
    feed = feedparser.parse(raw)
    if feed.bozo and not feed.entries:
        raise ValueError(f"could not parse feed: {feed.get('bozo_exception')}")

    source = feed.feed.get("title", "Unknown feed")
    articles = []
    for entry in feed.entries[:limit]:
        # Prefer full content; fall back to the summary most feeds provide.
        if entry.get("content"):
            body = entry.content[0].get("value", "")
        else:
            body = entry.get("summary", "")
        articles.append(
            Article(
                source=source,
                title=html_to_text(entry.get("title", "(untitled)")),
                link=entry.get("link", ""),
                published=_entry_datetime(entry),
                text=html_to_text(body),
            )
        )
    return articles


def fetch_feed(url: str, limit: int | None = None) -> list[Article]:
    return parse_feed(download(url), limit=limit)


def fetch_all(urls: list[str], limit: int | None = None) -> list[Article]:
    """Fetch every feed; a broken feed is logged and skipped instead of stopping the run."""
    articles = []
    for url in urls:
        try:
            articles.extend(fetch_feed(url, limit=limit))
        except Exception as exc:  # network errors, HTTP errors, unparsable feeds
            logger.warning("Skipping %s: %s", url, exc)
    return articles


def _entry_datetime(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)
