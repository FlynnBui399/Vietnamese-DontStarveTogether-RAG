"""Parse MediaWiki wikitext into cleaned hierarchical semantic sections."""

from __future__ import annotations

import re

import mwparserfromhell
from mwparserfromhell.nodes import Heading, Tag, Template, Wikilink
from mwparserfromhell.wikicode import Wikicode

from src.processing.models import ParsedPage, ParsedSection, SourcePage

TABLE_PATTERN = re.compile(r"(?ms)^\{\|.*?^\|\}\s*")
MAGIC_WORD_PATTERN = re.compile(r"__[^_\n]+__")
WHITESPACE_PATTERN = re.compile(r"[ \t]+")
BOILERPLATE_SECTIONS = {
    "assets",
    "character quotes",
    "external links",
    "gallery",
    "references",
    "see also",
    "skins",
    "translate",
    "trivia",
}
SKIPPED_TEMPLATE_MARKERS = (
    "clear",
    "exclusivity",
    "gallery",
    "nav",
    "pic",
    "quote",
    "scrapbook",
    "stub",
)
SKIPPED_INFOBOX_FIELDS = (
    "audio",
    "color",
    "gallery",
    "icon",
    "image",
    "picture",
    "sound",
    "width",
)


class WikiPageCleaner:
    """Keep factual text/structure while removing wiki presentation boilerplate."""

    def parse(self, source: SourcePage, wikitext: str) -> ParsedPage:
        """Return deterministic sections and classifier evidence for one revision."""
        normalized_tables = TABLE_PATTERN.sub(
            lambda match: f"\n\n{self._normalize_table(match.group(0))}\n\n",
            wikitext,
        )
        code = mwparserfromhell.parse(normalized_tables)
        categories = self._extract_categories(code)
        templates = tuple(
            dict.fromkeys(
                self._normalize_inline(str(template.name))
                for template in code.filter_templates(recursive=True)
                if self._normalize_inline(str(template.name))
            )
        )
        scope_hints = self._extract_scope_hints(code)
        infobox_facts = self._extract_infobox_facts(code)
        sections = self._extract_sections(code, infobox_facts)
        return ParsedPage(
            source=source,
            sections=sections,
            categories=categories,
            template_names=templates,
            scope_hints=scope_hints,
            infobox_facts=infobox_facts,
        )

    def _extract_sections(
        self,
        code: Wikicode,
        infobox_facts: tuple[str, ...],
    ) -> tuple[ParsedSection, ...]:
        output: list[ParsedSection] = []
        heading_stack: list[str] = []
        skipped_level: int | None = None
        raw_sections = code.get_sections(include_lead=True, include_headings=True, flat=True)
        for section_number, section in enumerate(raw_sections):
            section_copy = mwparserfromhell.parse(str(section))
            headings = section_copy.filter_headings(recursive=False)
            if headings:
                heading = headings[0]
                title = self._clean_heading(heading) or f"Section {section_number}"
                level = max(2, int(heading.level))
                if skipped_level is not None:
                    if level > skipped_level:
                        continue
                    skipped_level = None
                target_parent_count = level - 2
                heading_stack = heading_stack[:target_parent_count]
                heading_stack.append(title)
                section_copy.remove(heading)
                if self._is_boilerplate_section(title):
                    skipped_level = level
                    continue
                path = tuple(heading_stack)
            else:
                path = ("Overview",)

            content = self._clean_section_code(section_copy)
            if path == ("Overview",) and infobox_facts:
                infobox = "Infobox:\n" + "\n".join(f"- {fact}" for fact in infobox_facts)
                content = f"{infobox}\n\n{content}" if content else infobox
            if content.strip():
                output.append(ParsedSection(path=path, content=content))
        return tuple(output)

    def _clean_section_code(self, code: Wikicode) -> str:
        for tag in list(code.filter_tags(recursive=True)):
            if self._tag_name(tag) in {"gallery", "imagemap", "ref", "references"}:
                self._remove(code, tag)
        for link in list(code.filter_wikilinks(recursive=True)):
            title = self._normalize_inline(str(link.title)).casefold()
            if title.startswith(("category:", "file:", "image:")):
                self._remove(code, link)
        for template in reversed(code.filter_templates(recursive=True)):
            replacement = self._render_template(template)
            try:
                code.replace(template, replacement, recursive=True)
            except ValueError:
                continue

        stripped = code.strip_code(normalize=True, collapse=False)
        return self._normalize_blocks(MAGIC_WORD_PATTERN.sub("", stripped))

    def _extract_categories(self, code: Wikicode) -> tuple[str, ...]:
        categories: list[str] = []
        for link in code.filter_wikilinks(recursive=True):
            title = self._normalize_inline(str(link.title))
            if title.casefold().startswith("category:"):
                category = title.split(":", 1)[1].strip()
                if category and category not in categories:
                    categories.append(category)
        return tuple(categories)

    def _extract_scope_hints(self, code: Wikicode) -> tuple[str, ...]:
        hints: list[str] = []
        for template in code.filter_templates(recursive=True):
            if self._normalize_inline(str(template.name)).casefold() != "exclusivity":
                continue
            for parameter in template.params:
                value = self._plain_value(str(parameter.value))
                if value and value not in hints:
                    hints.append(value)
        return tuple(hints)

    def _extract_infobox_facts(self, code: Wikicode) -> tuple[str, ...]:
        facts: list[str] = []
        for template in code.filter_templates(recursive=True):
            template_name = self._normalize_inline(str(template.name))
            if "infobox" not in template_name.casefold():
                continue
            for parameter in template.params:
                field = self._normalize_inline(str(parameter.name))
                field_key = field.casefold()
                if (
                    not field
                    or field.isdigit()
                    or any(marker in field_key for marker in SKIPPED_INFOBOX_FIELDS)
                ):
                    continue
                value = self._plain_value(str(parameter.value))
                if not value or len(value) > 500:
                    continue
                fact = f"{field}: {value}"
                if fact not in facts:
                    facts.append(fact)
        return tuple(facts)

    def _render_template(self, template: Template) -> str:
        name = self._normalize_inline(str(template.name))
        name_key = name.casefold()
        if "infobox" in name_key or any(marker in name_key for marker in SKIPPED_TEMPLATE_MARKERS):
            return ""
        values: list[str] = []
        for parameter in template.params:
            value = self._plain_value(str(parameter.value))
            if value:
                values.append(value)
        if not values:
            return ""
        if name_key in {"damage", "health", "hunger", "insulation", "sanity", "temperature"}:
            return f"{name}: {'; '.join(values)}"
        if len(values) <= 3:
            return "; ".join(values)
        return ""

    def _normalize_table(self, table: str) -> str:
        caption: str | None = None
        headers: list[str] = []
        rows: list[list[str]] = []
        current: list[str] = []
        for raw_line in table.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("{|", "|}")):
                continue
            if line.startswith("|+"):
                caption = self._plain_value(line[2:])
                continue
            if line.startswith("|-"):
                if current:
                    rows.append(current)
                    current = []
                continue
            if line.startswith("!"):
                cells = self._table_cells(line[1:], "!!")
                if not headers:
                    headers = cells
                else:
                    if current:
                        rows.append(current)
                    current = cells
                continue
            if line.startswith("|"):
                current.extend(self._table_cells(line[1:], "||"))
        if current:
            rows.append(current)

        output = [f"Table: {caption}" if caption else "Table:"]
        for index, row in enumerate(rows, start=1):
            if headers:
                fields = [
                    f"{headers[cell_index]}: {value}"
                    for cell_index, value in enumerate(row)
                    if value and cell_index < len(headers)
                ]
                overflow = row[len(headers) :]
                fields.extend(value for value in overflow if value)
            else:
                fields = [value for value in row if value]
            if fields:
                output.append(f"Row {index}: " + "; ".join(fields))
        return "\n".join(output) if len(output) > 1 else ""

    def _table_cells(self, value: str, delimiter: str) -> list[str]:
        cells: list[str] = []
        for raw_cell in value.split(delimiter):
            cell = raw_cell.strip()
            if "|" in cell and "=" in cell.split("|", 1)[0]:
                cell = cell.split("|", 1)[1]
            cleaned = self._plain_value(cell)
            if cleaned:
                cells.append(cleaned)
        return cells

    def _plain_value(self, value: str) -> str:
        parsed = mwparserfromhell.parse(value)
        for link in list(parsed.filter_wikilinks(recursive=True)):
            title = self._normalize_inline(str(link.title)).casefold()
            if title.startswith(("file:", "image:")):
                self._remove(parsed, link)
        text = parsed.strip_code(normalize=True, collapse=True, keep_template_params=True)
        return self._normalize_inline(text)

    def _clean_heading(self, heading: Heading) -> str:
        parsed = mwparserfromhell.parse(str(heading.title))
        for template in reversed(parsed.filter_templates(recursive=True)):
            try:
                parsed.remove(template, recursive=True)
            except ValueError:
                continue
        for link in list(parsed.filter_wikilinks(recursive=True)):
            title = self._normalize_inline(str(link.title)).casefold()
            if title.startswith(("file:", "image:")):
                self._remove(parsed, link)
        return self._normalize_inline(parsed.strip_code(normalize=True, collapse=True))

    @staticmethod
    def _is_boilerplate_section(title: str) -> bool:
        normalized = title.casefold()
        return any(marker in normalized for marker in BOILERPLATE_SECTIONS)

    @staticmethod
    def _tag_name(tag: Tag) -> str:
        return str(tag.tag).strip().casefold()

    @staticmethod
    def _remove(code: Wikicode, node: Wikilink | Tag) -> None:
        try:
            code.remove(node, recursive=True)
        except ValueError:
            return

    @staticmethod
    def _normalize_inline(value: str) -> str:
        return WHITESPACE_PATTERN.sub(" ", value.replace("\xa0", " ")).strip()

    @classmethod
    def _normalize_blocks(cls, value: str) -> str:
        paragraphs: list[str] = []
        current: list[str] = []
        for raw_line in value.replace("\r\n", "\n").split("\n"):
            line = cls._normalize_inline(raw_line)
            if not line:
                if current:
                    paragraphs.append("\n".join(current))
                    current = []
                continue
            if line.startswith(("*", "#")):
                line = f"- {line.lstrip('*# ').strip()}"
            current.append(line)
        if current:
            paragraphs.append("\n".join(current))
        return "\n\n".join(paragraph for paragraph in paragraphs if paragraph.strip())
