"""Tests for the deliberately small chunking policy."""

import httpx
import pytest

from src.wiki import WikiClient, split_text


def test_split_text_uses_a_small_overlap() -> None:
    words = [f"w{index}" for index in range(10)]

    chunks = split_text(" ".join(words), target_words=6, overlap_words=2)

    assert chunks == [
        "w0 w1 w2 w3 w4 w5",
        "w4 w5 w6 w7 w8 w9",
    ]


def test_split_text_does_not_emit_an_overlap_only_tail() -> None:
    text = " ".join(f"w{index}" for index in range(6))

    assert split_text(text, target_words=6, overlap_words=2) == [text]


def test_split_text_rejects_invalid_sizes() -> None:
    with pytest.raises(ValueError, match="Invalid chunk size"):
        split_text("content", target_words=5, overlap_words=5)


def test_search_titles_returns_unique_mediawiki_titles() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["list"] == "search"
        assert request.url.params["srsearch"] == "football helmet"
        assert request.url.params["srlimit"] == "3"
        return httpx.Response(
            200,
            json={
                "query": {
                    "search": [
                        {"title": "Football Helmet"},
                        {"title": "Football Helmet"},
                        {"title": "Pig Skin"},
                    ]
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    wiki = WikiClient(
        api_url="https://dontstarve.wiki.gg/api.php",
        base_url="https://dontstarve.wiki.gg",
        user_agent="test",
        client=client,
    )

    assert wiki.search_titles("football helmet", limit=3) == (
        "Football Helmet",
        "Pig Skin",
    )
