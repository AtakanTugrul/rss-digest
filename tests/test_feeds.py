import io
from datetime import datetime, timezone

import pytest

from rss_digest import feeds
from rss_digest.feeds import fetch_all, html_to_text, load_feed_urls, parse_feed

RSS_SAMPLE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Example AI Blog</title>
  <item>
    <title>First &amp; best post</title>
    <link>https://example.com/1</link>
    <pubDate>Fri, 17 Oct 2026 10:00:00 GMT</pubDate>
    <description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;.&lt;/p&gt;&lt;p&gt;Second paragraph.&lt;/p&gt;</description>
  </item>
  <item>
    <title>Second post</title>
    <link>https://example.com/2</link>
    <description>Short text.</description>
  </item>
</channel></rss>"""

ATOM_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Blog</title>
  <entry>
    <title>Atom entry</title>
    <link href="https://example.org/a"/>
    <updated>2026-10-16T08:30:00Z</updated>
    <summary>Only a summary.</summary>
    <content type="html">&lt;p&gt;The full content.&lt;/p&gt;</content>
  </entry>
</feed>"""


def test_html_to_text_strips_tags_and_keeps_paragraphs():
    html = "<p>Hello <b>world</b> &amp; friends.</p><script>evil()</script><pre>x = 1</pre><p>Next</p>"
    assert html_to_text(html) == "Hello world & friends.\nNext"


def test_parse_rss_feed():
    articles = parse_feed(RSS_SAMPLE)
    assert len(articles) == 2
    first = articles[0]
    assert first.source == "Example AI Blog"
    assert first.title == "First & best post"
    assert first.link == "https://example.com/1"
    assert first.published == datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)
    assert first.text == "Hello world.\nSecond paragraph."
    assert articles[1].published is None


def test_parse_feed_respects_limit():
    assert len(parse_feed(RSS_SAMPLE, limit=1)) == 1


def test_atom_prefers_full_content_over_summary():
    [article] = parse_feed(ATOM_SAMPLE)
    assert article.text == "The full content."
    assert article.link == "https://example.org/a"
    # No <published>, so the date falls back to <updated>.
    assert article.published == datetime(2026, 10, 16, 8, 30, tzinfo=timezone.utc)


def test_load_feed_urls_skips_comments_and_blanks(tmp_path):
    path = tmp_path / "feeds.txt"
    path.write_text("# comment\n\nhttps://a.example/feed  # trailing\nhttps://b.example/rss\n")
    assert load_feed_urls(path) == ["https://a.example/feed", "https://b.example/rss"]


def test_fetch_all_skips_broken_feeds(monkeypatch, caplog):
    def fake_download(url):
        if "broken" in url:
            raise OSError("connection refused")
        return RSS_SAMPLE.encode()

    monkeypatch.setattr(feeds, "download", fake_download)
    articles = fetch_all(["https://broken.example", "https://ok.example"], limit=1)
    assert [a.link for a in articles] == ["https://example.com/1"]
    assert "Skipping https://broken.example" in caplog.text


def test_html_to_text_keeps_text_after_unclosed_pre():
    assert html_to_text("<p>Intro.</p><pre>code<p>Rest of the article.") == "Intro.\ncode\nRest of the article."


def test_html_to_text_unclosed_script_is_still_dropped():
    assert html_to_text("<p>Intro.</p><script>evil()") == "Intro."


def test_parse_feed_rejects_garbage():
    with pytest.raises(ValueError):
        parse_feed(b"this is not a feed")


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/feed"])
def test_download_rejects_non_http_urls(url):
    with pytest.raises(ValueError):
        feeds.download(url)


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeOpener:
    def __init__(self, body):
        self.body = body
        self.seen = {}

    def open(self, request, timeout):
        self.seen = {"agent": request.get_header("User-agent"), "timeout": timeout}
        return _FakeResponse(self.body)


def test_download_sends_user_agent_and_timeout(monkeypatch):
    opener = _FakeOpener(b"<rss/>")
    monkeypatch.setattr(feeds, "_opener", lambda: opener)
    assert feeds.download("https://example.com/feed") == b"<rss/>"
    assert opener.seen == {"agent": feeds.USER_AGENT, "timeout": feeds.TIMEOUT_SECONDS}


def test_download_rejects_oversized_feed(monkeypatch):
    monkeypatch.setattr(feeds, "MAX_FEED_BYTES", 10)
    monkeypatch.setattr(feeds, "_opener", lambda: _FakeOpener(b"x" * 11))
    with pytest.raises(ValueError, match="larger than"):
        feeds.download("https://example.com/feed")


@pytest.mark.parametrize("target", ["ftp://example.com/feed", "file:///etc/passwd"])
def test_redirects_to_non_http_urls_are_refused(target):
    handler = feeds._HttpOnlyRedirectHandler()
    request = feeds.urllib.request.Request("https://example.com/feed")
    with pytest.raises(ValueError):
        handler.redirect_request(request, None, 302, "Found", {}, target)


def test_redirects_to_https_are_followed():
    handler = feeds._HttpOnlyRedirectHandler()
    request = feeds.urllib.request.Request("http://example.com/feed")
    new = handler.redirect_request(request, None, 301, "Moved", {}, "https://example.com/feed")
    assert new.full_url == "https://example.com/feed"


def test_parse_feed_rejects_entity_declarations():
    bomb = '<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY a "lol">]><rss><channel><title>&a;</title></channel></rss>'
    with pytest.raises(ValueError, match="entities"):
        parse_feed(bomb.encode())


def test_html_to_text_separates_table_cells_and_list_items():
    assert html_to_text("<table><tr><td>a</td><td>b</td></tr></table><ul><li>x</li></ul>") == "a\nb\nx"


def test_untitled_feed_is_named_after_its_host():
    feed = '<rss version="2.0"><channel><item><title>t</title><description>d</description></item></channel></rss>'
    [article] = parse_feed(feed, feed_url="https://blog.example.com/rss")
    assert article.source == "blog.example.com"
    assert article.feed_url == "https://blog.example.com/rss"
