"""MediaWiki client contract tests using recorded response shapes."""

import json
from pathlib import Path
from typing import cast

import httpx

from src.ingestion.mediawiki_client import MediaWikiClient, PageReference

FIXTURES = Path("tests/fixtures/mediawiki")


def _fixture(name: str) -> dict[str, object]:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, object], payload)


def test_siteinfo_uses_identifying_headers_and_disposable_cache(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request, json=_fixture("siteinfo.json"))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = MediaWikiClient(
        api_url="https://dontstarve.wiki.gg/api.php",
        user_agent="DSTVietnameseAssistant/test (https://example.test/contact)",
        request_delay_seconds=0,
        cache_dir=tmp_path,
        client=http_client,
    )

    first = client.site_info()
    second = client.site_info()

    assert first == second
    assert first.site_name == "Don't Starve Wiki"
    assert first.namespaces[0] == ""
    assert first.rights_url == "https://creativecommons.org/licenses/by-sa/4.0"
    assert len(requests) == 1
    assert requests[0].headers["user-agent"].startswith("DSTVietnameseAssistant/test")
    assert requests[0].headers["accept-encoding"] == "gzip"
    assert requests[0].url.params["maxlag"] == "5"
    http_client.close()


def test_retry_recovers_from_temporary_rate_limit(tmp_path: Path) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, request=request, json={"error": "rate limited"})
        return httpx.Response(200, request=request, json=_fixture("siteinfo.json"))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = MediaWikiClient(
        api_url="https://dontstarve.wiki.gg/api.php",
        user_agent="DSTVietnameseAssistant/test (https://example.test/contact)",
        request_delay_seconds=0,
        max_retries=1,
        cache_dir=tmp_path,
        client=http_client,
        sleeper=sleeps.append,
    )

    assert client.site_info().generator == "MediaWiki 1.43.6"
    assert calls == 2
    assert sleeps == [0.5]
    http_client.close()


def test_fetch_page_preserves_revision_and_deterministic_storage_payload(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["pageids"] == "200315"
        assert "rvlimit" not in request.url.params
        return httpx.Response(200, request=request, json=_fixture("pages.json"))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = MediaWikiClient(
        api_url="https://dontstarve.wiki.gg/api.php",
        user_agent="DSTVietnameseAssistant/test (https://example.test/contact)",
        request_delay_seconds=0,
        cache_dir=tmp_path,
        client=http_client,
    )

    page = client.fetch_pages((PageReference(200315, "Football Helmet", 0),))[0]
    stored = json.loads(page.storage_bytes())

    assert page.revision_id == 377548
    assert page.storage_path == "pages/200315/377548.json"
    assert len(page.content_hash) == 64
    assert stored["metadata"]["content_hash"] == page.content_hash
    assert stored["response"]["query"]["pages"][0]["title"] == "Football Helmet"
    http_client.close()
