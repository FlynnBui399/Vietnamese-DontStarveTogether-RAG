"""Deterministic generation guardrails for comparison and evidence conflicts."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence

from src.generation.models import EvidenceConflict, EvidenceSource
from src.terminology.models import ResolvedEntity
from src.terminology.normalizer import normalize_search_text

COMPARISON_MARKERS = ("so sanh", "khac nhau", " vs ", " versus ", "compare")
STRUCTURED_FIELD = re.compile(r"^\s*(?:Field:\s*)?([^:\n]{2,60}):\s*([^\n]{1,120})\s*$", re.I)


def is_comparison_query(query: str) -> bool:
    """Identify explicit comparison requests without invoking an LLM classifier."""
    normalized = f" {normalize_search_text(query)} "
    return any(marker in normalized for marker in COMPARISON_MARKERS)


def missing_comparison_entities(
    query: str,
    entities: Sequence[ResolvedEntity],
    sources: Sequence[EvidenceSource],
) -> tuple[str, ...]:
    """Require one evidence page per resolved entity for explicit comparisons."""
    if not is_comparison_query(query) or len(entities) < 2:
        return ()
    pages = {source.page_title.casefold() for source in sources}
    return tuple(
        entity.entity_title for entity in entities if entity.entity_title.casefold() not in pages
    )


def detect_conflicts(sources: Sequence[EvidenceSource]) -> tuple[EvidenceConflict, ...]:
    """Detect different values for the same structured field on the same page."""
    grouped: defaultdict[tuple[str, str], defaultdict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    display: dict[tuple[str, str], tuple[str, str]] = {}
    for source in sources:
        for line in source.content.splitlines():
            match = STRUCTURED_FIELD.match(line)
            if match is None:
                continue
            field, value = (part.strip() for part in match.groups())
            key = (source.page_title.casefold(), normalize_search_text(field))
            grouped[key][value].add(source.id)
            display[key] = (source.page_title, field)
    conflicts: list[EvidenceConflict] = []
    for key, values in grouped.items():
        if len(values) < 2:
            continue
        page_title, field = display[key]
        conflicts.append(
            EvidenceConflict(
                page_title=page_title,
                field=field,
                values=tuple(sorted(values)),
                source_ids=tuple(
                    sorted({source_id for ids in values.values() for source_id in ids})
                ),
            )
        )
    return tuple(
        sorted(conflicts, key=lambda item: (item.page_title.casefold(), item.field.casefold()))
    )
