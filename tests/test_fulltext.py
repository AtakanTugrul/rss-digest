from datetime import datetime, timezone

import pytest

from rss_digest import feeds
from rss_digest.feeds import Article
from rss_digest.fulltext import extract_article_text, fill_short_articles

LONG = "This paragraph is long enough to count as part of the article body."

PAGE = f"""<html><head><script>var x = "{LONG}";</script></head><body>
<header><p>{LONG} (site header)</p></header>
<nav><p>{LONG} (menu)</p></nav>
<p>{LONG} (outside the article)</p>
<article>
  <h1>Title</h1>
  <p>Short byline.</p>
  <p>{LONG} One.</p>
  <p>{LONG} Two.
  <div>unclosed paragraph above ends here</div>
  <aside><p>{LONG} (sidebar)</p></aside>
</article>
<footer><p>{LONG} (footer)</p></footer>
</body></html>"""


def make(text, link="https://example.com/post"):
    return Article("Blog", "t", link, datetime(2026, 10, 1, tzinfo=timezone.utc), text)


def test_extract_prefers_article_paragraphs_and_skips_page_furniture():
    assert extract_article_text(PAGE) == f"{LONG} One.\n{LONG} Two."


def test_extract_falls_back_to_all_paragraphs_without_article_tag():
    html = f"<body><p>{LONG}</p><nav><p>{LONG} (menu)</p></nav><p>tiny</p></body>"
    assert extract_article_text(html) == LONG


def test_fill_short_articles_replaces_excerpts_only(monkeypatch):
    fetched = []

    def fake_download(url, public_only=False):
        assert public_only
        fetched.append(url)
        return PAGE.encode()

    monkeypatch.setattr(feeds, "download", fake_download)
    short, long_ = make("Just an excerpt."), make("x" * 600, link="https://example.com/long")
    result = fill_short_articles([short, long_])
    assert fetched == ["https://example.com/post"]
    assert result[0].text.startswith(LONG)
    assert result[1] is long_


def test_fill_short_articles_keeps_feed_text_on_errors(monkeypatch, caplog):
    def fake_download(url, public_only=False):
        raise OSError("timed out")

    monkeypatch.setattr(feeds, "download", fake_download)
    [article] = fill_short_articles([make("Just an excerpt.")])
    assert article.text == "Just an excerpt."
    assert "Keeping feed text" in caplog.text


def test_fill_short_articles_keeps_feed_text_when_page_has_less(monkeypatch):
    monkeypatch.setattr(feeds, "download", lambda url, public_only=False: b"<p>tiny</p>")
    [article] = fill_short_articles([make("Just an excerpt.")])
    assert article.text == "Just an excerpt."


def test_fill_short_articles_does_not_fetch_internal_addresses(monkeypatch):
    monkeypatch.setattr(feeds.socket, "getaddrinfo", lambda host, port: [(None, None, None, "", ("127.0.0.1", 0))])
    monkeypatch.setattr(feeds, "_public_opener", lambda: pytest.fail("internal address was fetched"))
    [article] = fill_short_articles([make("Just an excerpt.", link="http://localhost/admin")])
    assert article.text == "Just an excerpt."
