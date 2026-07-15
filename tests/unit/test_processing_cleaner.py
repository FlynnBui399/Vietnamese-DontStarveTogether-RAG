"""Wikitext cleaning and hierarchical section parsing tests."""

from pathlib import Path

from src.processing.cleaner import WikiPageCleaner
from src.processing.models import SourcePage

FIXTURE = Path("tests/fixtures/processing/football_helmet.wiki")


def _source(*, title: str = "Football Helmet") -> SourcePage:
    return SourcePage(
        id="00000000-0000-0000-0000-000000000100",
        mediawiki_page_id=200315,
        title=title,
        canonical_url="https://dontstarve.wiki.gg/wiki/Football_Helmet",
        revision_id=377548,
        revision_timestamp="2026-07-01T12:00:00Z",
        preliminary_game_scope="dst",
        raw_storage_bucket="dst-wiki-raw",
        raw_storage_path="pages/200315/377548.json",
        metadata={},
    )


def test_cleaner_preserves_infobox_table_and_heading_hierarchy() -> None:
    page = WikiPageCleaner().parse(_source(), FIXTURE.read_text(encoding="utf-8"))
    sections = {section.section_path: section.content for section in page.sections}

    assert page.categories == ("Armor", "Items", "Don't Starve Together")
    assert "Object Infobox" in page.template_names
    assert page.scope_hints == ("Don't Starve Together",)
    assert "name: Football Helmet" in page.infobox_facts
    assert "damage reduction: 80%" in page.infobox_facts
    assert "Overview" in sections
    assert "Crafting" in sections
    assert "Crafting > Tips" in sections
    assert "Gallery" not in sections
    assert not any("Alternate icons" in path for path in sections)
    assert "Table:" in sections["Crafting"]
    assert "Stat: Damage reduction" in sections["Crafting"]
    assert "Value: 80%" in sections["Crafting"]
    assert "{{" not in "\n".join(sections.values())
    assert "[[Category:" not in "\n".join(sections.values())
