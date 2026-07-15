"""Rule-based, evidence-backed page and section classification."""

from __future__ import annotations

import re
from collections.abc import Iterable

from src.processing.models import (
    EntityType,
    GameScope,
    PageClassification,
    ParsedPage,
    SourceKind,
)

SCOPE_RULES: tuple[tuple[GameScope, tuple[str, ...]], ...] = (
    ("dst", ("don't starve together", "return of them", "a new reign")),
    ("reign_of_giants", ("reign of giants",)),
    ("shipwrecked", ("shipwrecked",)),
    ("hamlet", ("hamlet",)),
    ("dont_starve", ("don't starve",)),
)
ENTITY_CATEGORY_RULES: tuple[tuple[EntityType, tuple[str, ...]], ...] = (
    ("boss", ("boss", "giants")),
    ("character", ("character", "survivors")),
    ("weapon", ("weapon",)),
    ("armor", ("armor", "armour")),
    ("tool", ("tool",)),
    ("recipe", ("crock pot recipes", "recipes")),
    ("food", ("food", "vegetable", "fruit", "meat", "perishables")),
    ("structure", ("structure", "crafting stations", "light sources")),
    ("mob", ("mobs", "creatures", "monsters", "animals")),
    ("mechanic", ("game mechanics", "mechanics")),
    ("biome", ("biomes", "caves")),
    ("season", ("seasons",)),
    ("guide", ("guides",)),
    ("update", ("updates",)),
    ("item", ("items", "objects", "resources")),
)


class PageClassifier:
    """Classify from explicit title/template/category evidence before text fallback."""

    def classify(self, page: ParsedPage) -> PageClassification:
        """Return page scope, entity type, source kind, and reasons."""
        game_scope, scope_reason = self._classify_scope(page)
        entity_type, entity_reason = self._classify_entity(page)
        source_kind, source_reason = self._classify_source(page, entity_type)
        return PageClassification(
            game_scope=game_scope,
            entity_type=entity_type,
            source_kind=source_kind,
            subjective=source_kind == "guide",
            scope_reason=scope_reason,
            entity_reason=entity_reason,
            source_reason=source_reason,
        )

    def classify_section_scope(
        self,
        page_scope: GameScope,
        section_path: str,
    ) -> GameScope:
        """Narrow mixed pages only when a heading names a specific game."""
        normalized = self._normalize(section_path)
        matches = self._scope_matches((normalized,))
        if len(matches) == 1:
            return next(iter(matches))
        if len(matches) > 1:
            return "mixed"
        return page_scope

    def _classify_scope(self, page: ParsedPage) -> tuple[GameScope, str]:
        title = self._normalize(page.source.title)
        if title.endswith("/dst") or title == "don't starve together":
            return "dst", "title"
        hint_matches = self._scope_matches(self._normalize(value) for value in page.scope_hints)
        if len(hint_matches) > 1:
            return "mixed", "exclusivity_template"
        if len(hint_matches) == 1:
            return next(iter(hint_matches)), "exclusivity_template"
        category_matches = self._scope_matches(self._normalize(value) for value in page.categories)
        if len(category_matches) > 1:
            return "mixed", "category"
        if len(category_matches) == 1:
            return next(iter(category_matches)), "category"
        return "unknown", "insufficient_scope_evidence"

    def _classify_entity(self, page: ParsedPage) -> tuple[EntityType, str]:
        categories = tuple(self._normalize(value) for value in page.categories)
        for entity_type, markers in ENTITY_CATEGORY_RULES:
            if any(marker in category for marker in markers for category in categories):
                return entity_type, "category"

        template_names = tuple(self._normalize(value) for value in page.template_names)
        template_rules: tuple[tuple[EntityType, str], ...] = (
            ("update", "update infobox"),
            ("biome", "biome infobox"),
            ("character", "character infobox"),
            ("mob", "creature infobox"),
            ("item", "object infobox"),
        )
        for entity_type, marker in template_rules:
            if any(marker in template for template in template_names):
                return entity_type, "infobox_template"

        title = self._normalize(page.source.title)
        if title.startswith("guides/"):
            return "guide", "title"
        return "other", "fallback"

    def _classify_source(
        self,
        page: ParsedPage,
        entity_type: EntityType,
    ) -> tuple[SourceKind, str]:
        title = self._normalize(page.source.title)
        templates = tuple(self._normalize(value) for value in page.template_names)
        if entity_type == "guide" or title.startswith("guides/"):
            return "guide", "guide_title_or_entity"
        if entity_type == "update" or any("update infobox" in value for value in templates):
            return "version_history", "update_template_or_entity"
        if title.startswith("category:"):
            return "category_list", "category_title"
        return "factual_article", "article_default"

    @staticmethod
    def _scope_matches(values: Iterable[str]) -> set[GameScope]:
        matches: set[GameScope] = set()
        for value in values:
            for scope, markers in SCOPE_RULES:
                if any(marker in value for marker in markers):
                    matches.add(scope)
                    break
        return matches

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()
