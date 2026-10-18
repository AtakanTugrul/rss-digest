"""Render summarized articles as a Markdown digest."""

from __future__ import annotations

import re
import urllib.parse
from datetime import date

from .feeds import Article
from .summarizer import summarize

# Feed content is untrusted: escape anything Markdown (or inline HTML) would
# interpret, so a title or summary can only ever render as plain text.
_INLINE_SPECIAL = re.compile(r"([\\`*_\[\]()<>&|~])")
_LINE_START_SPECIAL = re.compile(r"^[#=+-]")
_LINE_START_NUMBER = re.compile(r"^(\d+)\.")


def escape_markdown(text: str) -> str:
    text = " ".join(text.split())
    text = _INLINE_SPECIAL.sub(r"\\\1", text)
    # A leading "#", "-", "1." etc. would start a heading or a list.
    text = _LINE_START_SPECIAL.sub(r"\\\g<0>", text)
    return _LINE_START_NUMBER.sub(r"\1\\.", text)


def safe_url(link: str) -> str | None:
    """Return the link as a Markdown destination, or None unless it is plain http(s)."""
    link = link.strip()
    parts = urllib.parse.urlparse(link)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    # Angle brackets let the URL contain ")" safely; percent-encode what they can't hold.
    return "<" + urllib.parse.quote(link, safe="/:?#[]@!$&'()*+,;=%~") + ">"


def build_digest(articles: list[Article], max_sentences: int = 2, today: date | None = None) -> str:
    today = today or date.today()
    lines = [f"# AI Blog Digest — {today.isoformat()}", ""]

    if not articles:
        lines.append("_No articles found._")
        return "\n".join(lines) + "\n"

    # Group by source, keeping the order in which feeds were listed.
    by_source: dict[str, list[Article]] = {}
    for article in articles:
        by_source.setdefault(article.source, []).append(article)

    for source, group in by_source.items():
        lines += [f"## {escape_markdown(source)}", ""]
        for article in group:
            title = escape_markdown(article.title)
            url = safe_url(article.link)
            if url:
                title = f"[{title}]({url})"
            when = f" · {article.published:%Y-%m-%d}" if article.published else ""
            lines.append(f"### {title}{when}")
            lines.append("")
            summary = summarize(article.text, max_sentences)
            lines.append(escape_markdown(summary) if summary else "_No text available in the feed._")
            lines.append("")

    return "\n".join(lines)
