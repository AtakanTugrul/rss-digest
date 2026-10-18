from datetime import date, datetime, timezone

import pytest

from rss_digest.cli import main
from rss_digest.digest import build_digest
from rss_digest.feeds import Article


def make(source, title, text="Some text.", link="https://example.com"):
    return Article(source, title, link, datetime(2026, 10, 1, tzinfo=timezone.utc), text)


def test_digest_groups_by_source_in_feed_order():
    articles = [make("Blog B", "b1"), make("Blog A", "a1"), make("Blog B", "b2")]
    md = build_digest(articles, today=date(2026, 10, 18))
    assert md.startswith("# AI Blog Digest — 2026-10-18")
    assert md.index("## Blog B") < md.index("## Blog A")
    assert md.index("b2") < md.index("## Blog A")
    assert "### [b1](<https://example.com>) · 2026-10-01" in md


def test_digest_handles_missing_text_and_empty_input():
    md = build_digest([make("Blog", "t", text="")])
    assert "_No text available in the feed._" in md
    assert "_No articles found._" in build_digest([])


def test_cli_writes_output_file(tmp_path, monkeypatch):
    feeds_file = tmp_path / "feeds.txt"
    feeds_file.write_text("https://example.com/feed\n")
    monkeypatch.setattr("rss_digest.cli.fetch_all", lambda urls, limit: [make("Blog", "Hello")])

    out = tmp_path / "out" / "digest.md"
    assert main(["--feeds", str(feeds_file), "-o", str(out)]) == 0
    assert "### [Hello]" in out.read_text()


def test_cli_missing_feed_file_returns_error(tmp_path):
    assert main(["--feeds", str(tmp_path / "nope.txt")]) == 1


def test_digest_escapes_untrusted_feed_content():
    article = make(
        "Blog [x](https://evil.example)",
        "a](javascript:alert(1)) [x\n# Injected",
        text="<script>alert(1)</script> is shown as text. Second sentence here.",
        link="javascript:alert(1)",
    )
    md = build_digest([article])
    assert "## Blog \\[x\\]\\(https://evil.example\\)" in md
    # Unsafe link scheme: the title is kept as plain text, without a link.
    assert "### a\\]\\(javascript:alert\\(1\\)\\) \\[x # Injected · 2026-10-01" in md
    assert "](javascript" not in md
    assert "\n# Injected" not in md
    assert "<script>" not in md


def test_digest_link_with_spaces_and_parens_stays_intact():
    md = build_digest([make("Blog", "t", link="https://e.com/a b)c")])
    assert "### [t](<https://e.com/a%20b)c>)" in md


def test_cli_prints_to_stdout(tmp_path, monkeypatch, capsys):
    feeds_file = tmp_path / "feeds.txt"
    feeds_file.write_text("https://example.com/feed\n")
    monkeypatch.setattr("rss_digest.cli.fetch_all", lambda urls, limit: [make("Blog", "Hello")])
    assert main(["--feeds", str(feeds_file)]) == 0
    assert "### [Hello]" in capsys.readouterr().out


def test_cli_non_utf8_feed_file_returns_error(tmp_path):
    feeds_file = tmp_path / "feeds.txt"
    feeds_file.write_bytes(b"\xff\xfe\x00bad")
    assert main(["--feeds", str(feeds_file)]) == 1


@pytest.mark.parametrize("flag", ["--limit", "--sentences"])
def test_cli_rejects_values_below_one(flag):
    with pytest.raises(SystemExit):
        main([flag, "0"])
