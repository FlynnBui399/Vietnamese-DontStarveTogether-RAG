"""Load the version-controlled DST Vietnamese glossary."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import cast

from src.terminology.models import AliasRecord, AliasType
from src.terminology.normalizer import detect_query_language, normalize_search_text

DEFAULT_GLOSSARY_PATH = Path("data/glossary/dst_vi_glossary.csv")
ALIAS_TYPES: set[str] = {
    "official_title",
    "official_translation",
    "community_translation",
    "abbreviation",
    "common_misspelling",
    "descriptive_alias",
    "generated_candidate",
}
ALIAS_RANKING: dict[AliasType, tuple[int, float]] = {
    "official_title": (100, 1.0),
    "official_translation": (95, 1.0),
    "community_translation": (85, 0.95),
    "abbreviation": (80, 0.95),
    "common_misspelling": (70, 0.90),
    "descriptive_alias": (65, 0.90),
    "generated_candidate": (10, 0.50),
}


class GlossaryError(ValueError):
    """Raised when the repository glossary is malformed or ambiguous."""


class Glossary:
    """Validated alias records derived from the repository CSV source of truth."""

    def __init__(self, records: tuple[AliasRecord, ...]) -> None:
        if not records:
            raise GlossaryError("Glossary contains no alias records")
        self.records = records

    @classmethod
    def load(cls, path: Path = DEFAULT_GLOSSARY_PATH) -> Glossary:
        """Load canonical, Vietnamese, community, typo, and descriptive aliases."""
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {
                "english_term",
                "vietnamese_term",
                "aliases",
                "term_type",
                "notes",
                "verified",
            }
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                raise GlossaryError("Glossary header does not match the required schema")
            records: list[AliasRecord] = []
            for line_number, row in enumerate(reader, start=2):
                records.extend(cls._parse_row(row, line_number, path))
        deduplicated: dict[tuple[str, str], AliasRecord] = {}
        for record in records:
            key = (record.entity_title.casefold(), record.alias_normalized)
            current = deduplicated.get(key)
            if current is None or (record.verified, record.priority) > (
                current.verified,
                current.priority,
            ):
                deduplicated[key] = record
        return cls(tuple(sorted(deduplicated.values(), key=cls._sort_key)))

    @classmethod
    def _parse_row(
        cls,
        row: dict[str, str | None],
        line_number: int,
        path: Path,
    ) -> list[AliasRecord]:
        english_term = (row.get("english_term") or "").strip()
        vietnamese_term = (row.get("vietnamese_term") or "").strip()
        term_type = (row.get("term_type") or "other").strip()
        notes = (row.get("notes") or "").strip()
        verified = (row.get("verified") or "").strip().casefold() in {"1", "true", "yes"}
        if not english_term:
            raise GlossaryError(f"Glossary line {line_number} has no English canonical term")
        slug = re.sub(r"[^a-z0-9]+", "-", english_term.casefold()).strip("-")
        source = path.as_posix()
        values: list[tuple[str, AliasType, bool]] = [(english_term, "official_title", True)]
        if vietnamese_term:
            values.append((vietnamese_term, "community_translation", verified))
        for encoded in (row.get("aliases") or "").split(";"):
            encoded = encoded.strip()
            if not encoded:
                continue
            prefix, separator, alias = encoded.partition(":")
            if not separator or prefix not in ALIAS_TYPES or not alias.strip():
                raise GlossaryError(
                    f"Glossary line {line_number} alias must be '<alias_type>:<value>'"
                )
            alias_type = cast(AliasType, prefix)
            values.append(
                (alias.strip(), alias_type, verified and alias_type != "generated_candidate")
            )

        output: list[AliasRecord] = []
        for alias, alias_type, alias_verified in values:
            priority, confidence = ALIAS_RANKING[alias_type]
            output.append(
                AliasRecord(
                    entity_title=english_term,
                    entity_slug=slug,
                    alias=alias,
                    alias_normalized=normalize_search_text(alias),
                    language=detect_query_language(alias),
                    alias_type=alias_type,
                    priority=priority,
                    confidence=confidence,
                    verified=alias_verified,
                    source=source,
                    metadata={"term_type": term_type, "notes": notes},
                )
            )
        return output

    @staticmethod
    def _sort_key(record: AliasRecord) -> tuple[str, int, int, str]:
        return (
            record.entity_title.casefold(),
            -int(record.verified),
            -record.priority,
            record.alias_normalized,
        )
