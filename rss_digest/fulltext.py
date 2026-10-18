"""Fetch the article page when a feed only carries a short excerpt."""

from __future__ import annotations

import dataclasses
import logging
from html.parser import HTMLParser

from . import feeds
from .feeds import Article

logger = logging.getLogger(__name__)

# Feed text shorter than this is treated as an excerpt worth replacing.
MIN_FEED_CHARS = 500
# Shorter paragraphs are mostly bylines, captions and "Share this" links.
MIN_PARAGRAPH_CHARS = 40

# Page furniture that isn't part of the article body.
_SKIP_TAGS = {"script", "style", "noscript", "pre", "nav", "header", "footer", "aside", "form", "button", "svg"}
_MAIN_TAGS = {"article", "main"}
# Tags that end a paragraph even when its </p> is missing.
_PARAGRAPH_BREAKS = {"p", "div", "section", "li", "ul", "ol", "table", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}


class _ParagraphExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.paragraphs: list[tuple[bool, str]] = []  # (inside <article>/<main>, text)
        self._current: list[str] | None = None
        self._skip_stack: list[str] = []
        self._main_depth = 0

    def _finish(self) -> None:
        if self._current is not None:
            text = " ".join("".join(self._current).split())
            if text:
                self.paragraphs.append((self._main_depth > 0, text))
            self._current = None

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_stack.append(tag)
            return
        if tag in _MAIN_TAGS:
            self._main_depth += 1
        if tag in _PARAGRAPH_BREAKS:
            self._finish()
        if tag == "p" and not self._skip_stack:
            self._current = []

    def handle_endtag(self, tag):
        if tag in self._skip_stack:
            while self._skip_stack.pop() != tag:
                pass
            return
        if tag in _PARAGRAPH_BREAKS:
            self._finish()
        if tag in _MAIN_TAGS and self._main_depth:
            self._main_depth -= 1

    def handle_data(self, data):
        if self._current is not None and not self._skip_stack:
            self._current.append(data)

    def close(self):
        super().close()
        self._finish()


def extract_article_text(html: str) -> str:
    """Return the article's paragraphs, preferring those inside <article> or <main>."""
    parser = _ParagraphExtractor()
    parser.feed(html)
    parser.close()
    paragraphs = [(in_main, text) for in_main, text in parser.paragraphs if len(text) >= MIN_PARAGRAPH_CHARS]
    if any(in_main for in_main, _ in paragraphs):
        paragraphs = [p for p in paragraphs if p[0]]
    return "\n".join(text for _, text in paragraphs)


def fill_short_articles(articles: list[Article], min_chars: int = MIN_FEED_CHARS) -> list[Article]:
    """Replace short feed excerpts with the text of the linked page, when that is longer."""
    result = []
    for article in articles:
        if len(article.text) < min_chars and article.link:
            try:
                page = feeds.download(article.link).decode("utf-8", errors="replace")
                text = extract_article_text(page)
            except Exception as exc:  # network errors, HTTP errors, non-http(s) links
                logger.warning("Keeping feed text for %s: %s", article.link, exc)
            else:
                if len(text) > len(article.text):
                    article = dataclasses.replace(article, text=text)
        result.append(article)
    return result
