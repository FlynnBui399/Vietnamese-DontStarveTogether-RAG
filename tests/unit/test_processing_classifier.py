"""Evidence-priority tests for scope, entity, and source classification."""

from src.processing.classifier import PageClassifier
from src.processing.cleaner import WikiPageCleaner
from src.processing.models import SourcePage


def _source(title: str) -> SourcePage:
    return SourcePage(
        id=f"page-{title}",
        mediawiki_page_id=1,
        title=title,
        canonical_url="https://dontstarve.wiki.gg/wiki/Test",
        revision_id=2,
        revision_timestamp=None,
        preliminary_game_scope="dst",
        raw_storage_bucket="dst-wiki-raw",
        raw_storage_path="pages/1/2.json",
        metadata={},
    )


def test_exclusivity_and_category_rules_classify_mixed_recipe() -> None:
    wikitext = """
{{Object Infobox|name=Asparagus}}
{{Exclusivity|Hamlet|Don't Starve Together}}
Asparagus is food.
[[Category:Crock Pot Recipes]]
[[Category:Don't Starve Together]]
"""
    parsed = WikiPageCleaner().parse(_source("Asparagus"), wikitext)

    classification = PageClassifier().classify(parsed)

    assert classification.game_scope == "mixed"
    assert classification.scope_reason == "exclusivity_template"
    assert classification.entity_type == "recipe"
    assert classification.source_kind == "factual_article"


def test_dst_suffix_and_update_template_have_priority() -> None:
    parsed = WikiPageCleaner().parse(
        _source("An Eye for An Eye/DST"),
        "{{Update Infobox|name=An Eye for An Eye}}\nUpdate details.",
    )

    classification = PageClassifier().classify(parsed)

    assert classification.game_scope == "dst"
    assert classification.scope_reason == "title"
    assert classification.entity_type == "update"
    assert classification.source_kind == "version_history"


def test_mixed_page_section_scope_is_narrowed_only_by_heading() -> None:
    classifier = PageClassifier()

    assert classifier.classify_section_scope("mixed", "Don't Starve Together") == "dst"
    assert classifier.classify_section_scope("mixed", "Usage") == "mixed"
