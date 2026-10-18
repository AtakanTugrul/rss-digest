from rss_digest.summarizer import split_sentences, summarize


def test_split_sentences():
    text = "First one. Second one! Is this third? Yes.\nNew paragraph here"
    assert split_sentences(text) == [
        "First one.",
        "Second one!",
        "Is this third?",
        "Yes.",
        "New paragraph here",
    ]


def test_split_sentences_does_not_break_on_decimals():
    assert split_sentences("Accuracy rose to 92.5 percent. Nice.") == ["Accuracy rose to 92.5 percent.", "Nice."]


def test_short_text_is_returned_whole():
    assert summarize("Only one sentence.", max_sentences=2) == "Only one sentence."


def test_empty_text():
    assert summarize("") == ""


def test_citations_do_not_make_a_sentence_important():
    text = (
        "Agents learn to compress their memory into short beliefs. "
        "Related work exists (Smith et al., 2025, Jones et al., 2024, Lee et al., 2023). "
        "Compressed beliefs let agents act over long horizons with less memory."
    )
    summary = summarize(text, max_sentences=2)
    assert "et al" not in summary


def test_summary_picks_on_topic_sentences_in_original_order():
    text = (
        "Language models keep getting better at reasoning. "
        "The weather was nice yesterday. "
        "New language models use reasoning traces during training. "
        "Lunch was served at noon. "
        "Reasoning benchmarks show language models improving fast."
    )
    summary = summarize(text, max_sentences=2)
    assert "weather" not in summary and "Lunch" not in summary
    sentences = split_sentences(summary)
    assert len(sentences) == 2
    # Original order is preserved.
    assert text.index(sentences[0]) < text.index(sentences[1])
