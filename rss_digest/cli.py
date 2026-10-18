"""Command-line entry point: `python -m rss_digest`."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .digest import build_digest
from .feeds import fetch_all, load_feed_urls


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="rss_digest",
        description="Fetch AI blog RSS feeds and write a short Markdown digest.",
    )
    parser.add_argument("--feeds", default="feeds.txt", help="file with one feed URL per line (default: feeds.txt)")
    parser.add_argument("--limit", type=int, default=3, help="latest posts to take from each feed (default: 3)")
    parser.add_argument("--sentences", type=int, default=2, help="sentences per summary (default: 2)")
    parser.add_argument("-o", "--output", help="write the digest to this file instead of stdout")
    args = parser.parse_args(argv)
    if args.limit < 1 or args.sentences < 1:
        parser.error("--limit and --sentences must be at least 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        urls = load_feed_urls(args.feeds)
    except (OSError, UnicodeDecodeError) as exc:
        logging.error("Cannot read feed list: %s", exc)
        return 1

    articles = fetch_all(urls, limit=args.limit)
    digest = build_digest(articles, max_sentences=args.sentences)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(digest, encoding="utf-8")
        logging.info("Wrote %d articles to %s", len(articles), args.output)
    else:
        sys.stdout.write(digest)
    return 0
