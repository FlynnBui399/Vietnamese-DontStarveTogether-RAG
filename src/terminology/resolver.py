"""Priority-aware exact and fuzzy entity resolution with bounded query expansion."""

from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher

from src.terminology.models import AliasRecord, ExpandedQuery, MatchType, ResolvedEntity
from src.terminology.normalizer import normalize_query, normalize_search_text, normalize_unicode


class AliasResolver:
    """Resolve entities while ensuring verified aliases outrank generated candidates."""

    def __init__(self, aliases: tuple[AliasRecord, ...], *, fuzzy_threshold: float = 0.78) -> None:
        if not 0.0 < fuzzy_threshold <= 1.0:
            raise ValueError("Fuzzy threshold must be in (0, 1]")
        self.aliases = aliases
        self.fuzzy_threshold = fuzzy_threshold

    def resolve(self, value: str, *, limit: int = 3) -> tuple[ResolvedEntity, ...]:
        """Return the best distinct entity matches for one user phrase."""
        query = normalize_search_text(value)
        if not query or limit <= 0:
            return ()
        candidates: list[ResolvedEntity] = []
        for alias in self.aliases:
            similarity = SequenceMatcher(None, query, alias.alias_normalized).ratio()
            match_type: MatchType
            tier: int
            if query == alias.alias_normalized:
                match_type = (
                    "exact_title" if alias.alias_type == "official_title" else "exact_alias"
                )
                tier = 4
                similarity = 1.0
            elif min(len(query), len(alias.alias_normalized)) >= 3 and (
                alias.alias_normalized.startswith(query)
                or query.startswith(alias.alias_normalized)
                or f" {alias.alias_normalized} " in f" {query} "
            ):
                match_type = "prefix"
                tier = 2
            elif similarity >= self.fuzzy_threshold:
                match_type = "fuzzy"
                tier = 1
            else:
                continue
            score = tier * 1000.0 + int(alias.verified) * 100.0 + alias.priority + similarity
            candidates.append(
                ResolvedEntity(
                    entity_title=alias.entity_title,
                    entity_slug=alias.entity_slug,
                    matched_alias=alias.alias,
                    alias_type=alias.alias_type,
                    match_type=match_type,
                    verified=alias.verified,
                    confidence=alias.confidence * similarity,
                    score=score,
                )
            )

        candidates.sort(
            key=lambda candidate: (
                candidate.score,
                candidate.confidence,
                candidate.entity_title.casefold(),
            ),
            reverse=True,
        )
        distinct: list[ResolvedEntity] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = candidate.entity_title.casefold()
            if key in seen:
                continue
            seen.add(key)
            distinct.append(candidate)
            if len(distinct) == limit:
                break
        return tuple(distinct)


class QueryExpander:
    """Expand a query only from deterministic repository aliases."""

    def __init__(self, resolver: AliasResolver, *, max_terms: int = 12) -> None:
        if max_terms < 2:
            raise ValueError("Query expansion must allow at least two terms")
        self.resolver = resolver
        self.max_terms = max_terms
        aliases_by_entity: defaultdict[str, list[AliasRecord]] = defaultdict(list)
        for alias in resolver.aliases:
            aliases_by_entity[alias.entity_title.casefold()].append(alias)
        self._aliases_by_entity = dict(aliases_by_entity)

    def expand(self, value: str, *, entity_limit: int = 2) -> ExpandedQuery:
        """Return normalized variants and high-confidence aliases without LLM invention."""
        query = normalize_query(value)
        resolved = self.resolver.resolve(value, limit=entity_limit)
        terms: list[str] = []
        self._append_unique(terms, normalize_unicode(value))
        self._append_unique(terms, query.search_normalized)
        for entity in resolved:
            self._append_unique(terms, entity.entity_title)
            aliases = self._aliases_by_entity.get(entity.entity_title.casefold(), [])
            aliases = sorted(
                aliases,
                key=lambda alias: (alias.verified, alias.priority, alias.confidence),
                reverse=True,
            )
            for alias in aliases:
                if alias.verified:
                    self._append_unique(terms, alias.alias)
                if len(terms) >= self.max_terms:
                    break
            if len(terms) >= self.max_terms:
                break
        return ExpandedQuery(query=query, resolved_entities=resolved, terms=tuple(terms))

    @staticmethod
    def _append_unique(terms: list[str], value: str) -> None:
        value = value.strip()
        normalized = normalize_search_text(value)
        if (
            value
            and normalized
            and all(normalize_search_text(term) != normalized for term in terms)
        ):
            terms.append(value)
