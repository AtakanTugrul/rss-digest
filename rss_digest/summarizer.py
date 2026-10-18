"""A small frequency-based extractive summarizer.

Each sentence is scored by how often its meaningful words appear in the whole
text. The highest-scoring sentences are returned in their original order, so
the summary still reads naturally. No external models or APIs are involved.
"""

from __future__ import annotations

import re
from collections import Counter

STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are as at be because been
    before being below between both but by can could did do does doing down during
    each few for from further had has have having he her here hers herself him
    himself his how i if in into is it its itself just let me more most my myself
    no nor not now of off on once only or other our ours ourselves out over own
    same she should so some such than that the their theirs them themselves then
    there these they this those through to too under until up very was we were
    what when where which while who whom why will with would you your yours
    yourself yourselves also us new one two may might must use used using via
    et al eg ie etc
    """.split()
)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[\"'“(\[]?[A-Z0-9])")
# Words must start with a letter, so years and numbers in citations don't count.
_WORD = re.compile(r"[a-z][a-z0-9'-]*")
# Parenthesized asides such as "(Smith et al., 2025)" add words but not meaning.
_PARENTHETICAL = re.compile(r"\([^()]*\)")
# Opening sentences usually state the point of a post, so they get a small boost.
_LEAD_BONUS = (0.3, 0.15)


# A piece ending like this was split at an abbreviation ("Dr. Smith") or at
# initials ("the U.S. Army"), not at the end of a sentence. Initials need at
# least two letters, so "plan B." still ends a sentence. The trade-off: a
# sentence that really ends in "U.S." gets joined to the next one.
_ABBREVIATION_END = re.compile(
    r"(?:\b(?:[Dd]r|[Mm]rs?|[Mm]s|[Pp]rof|[Ss]t|[Jj]r|[Ss]r|vs|[Ff]igs?|[Ii]nc|[Ll]td|approx)|\b[A-Z]\.(?:[A-Z]\.)*[A-Z])\.$"
)
# Only the end of a piece is checked, so long or hostile text stays linear.
_ABBREVIATION_TAIL = 32


def split_sentences(text: str) -> list[str]:
    sentences = []
    for paragraph in text.splitlines():
        merged: list[list[str]] = []
        for piece in (s.strip() for s in _SENTENCE_END.split(paragraph)):
            if not piece:
                continue
            if merged and _ABBREVIATION_END.search(merged[-1][-1][-_ABBREVIATION_TAIL:]):
                merged[-1].append(piece)
            else:
                merged.append([piece])
        sentences.extend(" ".join(parts) for parts in merged)
    return sentences


def _content_words(sentence: str) -> list[str]:
    sentence = _PARENTHETICAL.sub(" ", sentence.lower())
    return [w for w in _WORD.findall(sentence) if w not in STOPWORDS and len(w) > 1]


def summarize(text: str, max_sentences: int = 2) -> str:
    """Return the `max_sentences` most representative sentences of `text`."""
    sentences = split_sentences(text)
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    frequencies = Counter(w for s in sentences for w in _content_words(s))
    if not frequencies:
        return " ".join(sentences[:max_sentences])
    top = max(frequencies.values())

    def score(index: int) -> float:
        words = _content_words(sentences[index])
        if not words:
            return 0.0
        # Dividing by sqrt(length) keeps long sentences from winning just by being long.
        base = sum(frequencies[w] / top for w in words) / len(words) ** 0.5
        bonus = _LEAD_BONUS[index] if index < len(_LEAD_BONUS) else 0.0
        return base * (1 + bonus)

    ranked = sorted(range(len(sentences)), key=score, reverse=True)
    chosen = sorted(ranked[:max_sentences])
    return " ".join(sentences[i] for i in chosen)
