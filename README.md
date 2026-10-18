# rss-digest

A small command-line tool that fetches RSS/Atom feeds from AI blogs and turns
the latest posts into a short Markdown digest — with a summarizer written from
scratch, no paid APIs or ML models.

```
feeds.txt ──► fetch & parse (feedparser) ──► HTML → plain text ──► extractive summary ──► digest.md
```

## Example output

```markdown
# AI Blog Digest — 2026-10-18

## Example AI Lab Blog

### [Teaching small models to say "I don't know"](<https://example.com/blog/small-models-uncertainty>) · 2026-10-13

Small language models often answer confidently even when they are wrong. We trained a
3B-parameter model to flag low-confidence answers and cut its error rate on unanswerable
questions by half.
```

*(The sample above is made up for illustration; real output uses the posts from your feeds.)*

## Quick start

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m rss_digest                      # print the digest to the terminal
python -m rss_digest -o output/digest.md  # or save it to a file
```

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--feeds PATH` | `feeds.txt` | File with one feed URL per line (`#` starts a comment) |
| `--limit N` | `3` | Latest posts to take from each feed |
| `--sentences N` | `2` | Sentences per summary |
| `-o, --output PATH` | stdout | Write the digest to a file |
| `--full-text` | off | When a feed only has a short excerpt, fetch the article page and summarize its text |

Edit [`feeds.txt`](feeds.txt) to follow different blogs. A feed that is down or
broken is skipped with a warning; the rest of the digest is still produced.

Feed content is treated as untrusted: titles and summaries are Markdown-escaped,
only `http(s)` links are rendered and followed (redirects included), feeds that
declare XML entities are refused, and each download is capped at 5 MB and
30 seconds. With `--full-text`, article links are fetched only from
public addresses: the host, every redirect and the address actually connected
to are checked, so loopback, private and link-local addresses are refused even
if DNS changes between the check and the connection. These requests ignore
proxy settings, so the checked address is the real server's.

## How the summarizer works

[`rss_digest/summarizer.py`](rss_digest/summarizer.py) implements a classic
**frequency-based extractive summarizer**:

1. Split the post into sentences.
2. Count how often each meaningful word appears in the whole post (common
   words like "the" or "and", numbers, and parenthesized citations are ignored).
3. Score each sentence by the average frequency of its words, divided by the
   square root of its length so long sentences don't win just by being long.
   The first two sentences get a small boost, since posts usually open with
   their main point.
4. Return the top-scoring sentences **in their original order**.

Extractive means the summary only uses sentences from the post itself, so it
never invents facts — the trade-off is that it can't rephrase. Many feeds only
include a short excerpt rather than the full post; with `--full-text` the tool
then fetches the post's page and keeps the paragraphs inside `<article>`/`<main>`,
skipping navigation, headers, footers and sidebars.

## Project layout

```
rss_digest/
  feeds.py        fetch feeds, parse entries, strip HTML
  summarizer.py   extractive summarizer
  fulltext.py     fetch the article page when the feed text is short
  digest.py       Markdown rendering
  cli.py          command-line interface
tests/            unit tests (no network needed)
feeds.txt         feed list
```

## Running the tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The tests use inline sample feeds and stub out the network, so they run
offline in well under a second.

## Possible next steps

- Skip posts already included in a previous digest
- Run daily with GitHub Actions and commit the digest

## License

MIT
