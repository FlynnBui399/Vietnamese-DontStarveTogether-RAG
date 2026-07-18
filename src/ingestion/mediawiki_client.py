"""Polite MediaWiki Action API client for discovery and raw page retrieval."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RETRYABLE_API_ERRORS = {"maxlag", "ratelimited", "readonly"}


class MediaWikiError(RuntimeError):
    """Raised when the Action API returns an invalid or terminal response."""


@dataclass(frozen=True, slots=True)
class SiteInfo:
    """MediaWiki identity, namespace, and licensing information."""

    api_url: str
    site_name: str
    generator: str
    server: str
    article_path: str
    language: str
    rights_text: str | None
    rights_url: str | None
    namespaces: dict[int, str]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable site-information report."""
        return {
            "api_url": self.api_url,
            "site_name": self.site_name,
            "generator": self.generator,
            "server": self.server,
            "article_path": self.article_path,
            "language": self.language,
            "rights_text": self.rights_text,
            "rights_url": self.rights_url,
            "namespaces": {str(key): value for key, value in self.namespaces.items()},
        }


@dataclass(frozen=True, slots=True)
class PageReference:
    """A page or subcategory returned during discovery."""

    page_id: int
    title: str
    namespace: int
    member_type: str = "page"


@dataclass(frozen=True, slots=True)
class RawWikiPage:
    """One latest revision and its verbatim page object from the Action API."""

    page_id: int
    title: str
    namespace: int
    canonical_url: str
    revision_id: int
    revision_timestamp: str
    mediawiki_sha1: str
    content_model: str
    content: str
    retrieved_at: str
    api_url: str
    raw_page: dict[str, Any]

    @property
    def content_hash(self) -> str:
        """Return the SHA-256 used by the knowledge schema."""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    @property
    def storage_path(self) -> str:
        """Return the deterministic raw-object path."""
        return f"pages/{self.page_id}/{self.revision_id}.json"

    def storage_bytes(self) -> bytes:
        """Serialize the raw API page with retrieval metadata as deterministic UTF-8 JSON."""
        payload = {
            "metadata": {
                "api_url": self.api_url,
                "page_id": self.page_id,
                "revision_id": self.revision_id,
                "title": self.title,
                "content_hash": self.content_hash,
                "retrieved_at": self.retrieved_at,
            },
            "response": {"query": {"pages": [self.raw_page]}},
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")


class MediaWikiClient:
    """Serial Action API client with throttling, retry, gzip, and disposable caching."""

    def __init__(
        self,
        *,
        api_url: str,
        user_agent: str,
        request_delay_seconds: float = 0.5,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        cache_dir: Path = Path("data/cache/mediawiki"),
        cache_ttl_seconds: int = 3600,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("A descriptive MediaWiki User-Agent is required")
        if request_delay_seconds < 0:
            raise ValueError("request_delay_seconds cannot be negative")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self.api_url = api_url
        self.request_delay_seconds = request_delay_seconds
        self.max_retries = max_retries
        self.cache_dir = cache_dir
        self.cache_ttl_seconds = cache_ttl_seconds
        self._sleeper = sleeper
        self._monotonic = monotonic
        self._last_request_at: float | None = None
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._client.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            }
        )

    def __enter__(self) -> MediaWikiClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def site_info(self) -> SiteInfo:
        """Verify the endpoint and inspect site, namespace, and license information."""
        payload = self._request(
            {
                "action": "query",
                "meta": "siteinfo",
                "siprop": "general|namespaces|rightsinfo",
            },
            use_cache=True,
        )
        query = self._mapping(payload, "query")
        general = self._mapping(query, "general")
        rights = query.get("rightsinfo")
        rights_mapping = rights if isinstance(rights, dict) else {}
        namespaces_payload = self._mapping(query, "namespaces")
        namespaces: dict[int, str] = {}
        for key, value in namespaces_payload.items():
            if isinstance(value, dict):
                namespaces[int(key)] = str(value.get("name", ""))

        return SiteInfo(
            api_url=self.api_url,
            site_name=str(general["sitename"]),
            generator=str(general["generator"]),
            server=str(general["server"]),
            article_path=str(general["articlepath"]),
            language=str(general["lang"]),
            rights_text=self._optional_string(rights_mapping.get("text")),
            rights_url=self._optional_string(rights_mapping.get("url")),
            namespaces=namespaces,
        )

    def resolve_titles(self, titles: Sequence[str]) -> list[PageReference]:
        """Resolve seed titles to canonical page IDs without downloading content."""
        references: list[PageReference] = []
        for batch in self._batches(titles, 50):
            payload = self._request(
                {
                    "action": "query",
                    "prop": "info",
                    "inprop": "url",
                    "redirects": "1",
                    "titles": "|".join(batch),
                },
                use_cache=True,
            )
            pages = self._pages(payload)
            for page in pages:
                if page.get("missing") is True or "pageid" not in page:
                    continue
                references.append(
                    PageReference(
                        page_id=int(page["pageid"]),
                        title=str(page["title"]),
                        namespace=int(page["ns"]),
                    )
                )
        return references

    def category_members(self, category: str, *, limit: int) -> list[PageReference]:
        """List a bounded number of direct members, following API continuation tokens."""
        if limit <= 0:
            return []
        members: list[PageReference] = []
        continuation: dict[str, str] = {}
        while len(members) < limit:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": category,
                "cmprop": "ids|title|type",
                "cmlimit": str(min(500, limit - len(members))),
                **continuation,
            }
            payload = self._request(params, use_cache=True)
            query = self._mapping(payload, "query")
            raw_members = query.get("categorymembers")
            if not isinstance(raw_members, list):
                raise MediaWikiError("MediaWiki response did not contain categorymembers")
            for member in raw_members:
                if not isinstance(member, dict):
                    continue
                members.append(
                    PageReference(
                        page_id=int(member["pageid"]),
                        title=str(member["title"]),
                        namespace=int(member["ns"]),
                        member_type=str(member.get("type", "page")),
                    )
                )
                if len(members) >= limit:
                    break
            raw_continue = payload.get("continue")
            if not isinstance(raw_continue, dict) or "cmcontinue" not in raw_continue:
                break
            continuation = {str(key): str(value) for key, value in raw_continue.items()}
        return members

    def fetch_pages(self, references: Sequence[PageReference]) -> list[RawWikiPage]:
        """Fetch latest revision metadata and wikitext for discovered page IDs in batches."""
        fetched: list[RawWikiPage] = []
        for batch in self._batches(references, 20):
            payload = self._request(
                {
                    "action": "query",
                    "prop": "info|revisions",
                    "inprop": "url",
                    "pageids": "|".join(str(reference.page_id) for reference in batch),
                    "rvprop": "ids|timestamp|sha1|content|contentmodel",
                    "rvslots": "main",
                },
                use_cache=False,
            )
            for page in self._pages(payload):
                raw_revisions = page.get("revisions")
                if not isinstance(raw_revisions, list) or not raw_revisions:
                    continue
                revision = raw_revisions[0]
                if not isinstance(revision, dict):
                    continue
                slots = revision.get("slots")
                main = slots.get("main") if isinstance(slots, dict) else None
                if not isinstance(main, dict):
                    raise MediaWikiError(f"Page {page.get('title')} has no main revision slot")
                content = main.get("content")
                if not isinstance(content, str):
                    raise MediaWikiError(f"Page {page.get('title')} has no revision content")
                fetched.append(
                    RawWikiPage(
                        page_id=int(page["pageid"]),
                        title=str(page["title"]),
                        namespace=int(page["ns"]),
                        canonical_url=str(page["fullurl"]),
                        revision_id=int(revision["revid"]),
                        revision_timestamp=str(revision["timestamp"]),
                        mediawiki_sha1=str(revision["sha1"]),
                        content_model=str(main.get("contentmodel", "wikitext")),
                        content=content,
                        retrieved_at=datetime.now(UTC).isoformat(),
                        api_url=self.api_url,
                        raw_page=page,
                    )
                )
        return fetched

    def _request(self, params: dict[str, str], *, use_cache: bool) -> dict[str, Any]:
        full_params = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
        cache_path = self._cache_path(full_params)
        if use_cache:
            cached = self._read_cache(cache_path)
            if cached is not None:
                return cached

        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                response = self._client.get(self.api_url, params=full_params)
                self._last_request_at = self._monotonic()
                if response.status_code in RETRYABLE_STATUS_CODES:
                    raise httpx.HTTPStatusError(
                        "Retryable MediaWiki response",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise MediaWikiError("MediaWiki returned a non-object JSON response")
                error = payload.get("error")
                if isinstance(error, dict):
                    code = str(error.get("code", "unknown"))
                    if code in RETRYABLE_API_ERRORS:
                        raise MediaWikiError(f"retryable:{code}")
                    raise MediaWikiError(f"MediaWiki API error {code}: {error.get('info', '')}")
            except (httpx.HTTPError, MediaWikiError) as exc:
                if attempt >= self.max_retries or not self._is_retryable(exc):
                    raise MediaWikiError(f"MediaWiki request failed: {exc}") from exc
                self._sleeper(0.5 * (2**attempt))
                continue

            if use_cache:
                self._write_cache(cache_path, payload)
            return payload

        raise AssertionError("retry loop exited unexpectedly")

    def _throttle(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self.request_delay_seconds - (self._monotonic() - self._last_request_at)
        if remaining > 0:
            self._sleeper(remaining)

    def _cache_path(self, params: dict[str, str]) -> Path:
        material = json.dumps(
            {"api_url": self.api_url, "params": params},
            sort_keys=True,
            separators=(",", ":"),
        )
        return self.cache_dir / f"{hashlib.sha256(material.encode()).hexdigest()}.json"

    def _read_cache(self, path: Path) -> dict[str, Any] | None:
        if self.cache_ttl_seconds <= 0 or not path.exists():
            return None
        if time.time() - path.stat().st_mtime > self.cache_ttl_seconds:
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _write_cache(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in RETRYABLE_STATUS_CODES
        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        return isinstance(exc, MediaWikiError) and str(exc).startswith("retryable:")

    @staticmethod
    def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
        value = payload.get(key)
        if not isinstance(value, dict):
            raise MediaWikiError(f"MediaWiki response did not contain {key}")
        return value

    @classmethod
    def _pages(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        query = cls._mapping(payload, "query")
        pages = query.get("pages")
        if not isinstance(pages, list):
            raise MediaWikiError("MediaWiki response did not contain pages")
        return [page for page in pages if isinstance(page, dict)]

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return str(value) if value is not None else None

    @staticmethod
    def _batches[T](values: Sequence[T], size: int) -> Iterator[Sequence[T]]:
        for offset in range(0, len(values), size):
            yield values[offset : offset + size]
