"""Validate completeness and remove explicitly reported exact duplicate chunks."""

from __future__ import annotations

from collections.abc import Iterable

from src.processing.models import ChunkDraft, ValidationIssue, ValidationReport


class CorpusValidator:
    """Enforce Milestone 3 chunk invariants before any database insert."""

    def validate(
        self,
        chunks: Iterable[ChunkDraft],
        *,
        expected_page_ids: set[str],
    ) -> ValidationReport:
        """Return only valid, first-seen chunks and a complete findings report."""
        candidates = list(chunks)
        valid: list[ChunkDraft] = []
        issues: list[ValidationIssue] = []
        source_keys: set[str] = set()
        body_hash_to_source: dict[str, str] = {}
        duplicate_count = 0
        empty_count = 0
        complete_count = 0

        for chunk in candidates:
            missing = self._missing_metadata(chunk)
            if not chunk.content.strip():
                empty_count += 1
                issues.append(
                    ValidationIssue("empty_chunk", "Chunk content is empty", chunk.source_key)
                )
                continue
            if missing:
                issues.append(
                    ValidationIssue(
                        "missing_metadata",
                        f"Missing required metadata: {', '.join(missing)}",
                        chunk.source_key,
                    )
                )
                continue
            complete_count += 1
            if chunk.source_key in source_keys:
                duplicate_count += 1
                issues.append(
                    ValidationIssue(
                        "duplicate_source_key",
                        "Duplicate deterministic source key was excluded",
                        chunk.source_key,
                        fatal=False,
                    )
                )
                continue
            body_hash = str(chunk.metadata.get("body_hash", ""))
            duplicate_of = body_hash_to_source.get(body_hash)
            if body_hash and duplicate_of is not None:
                duplicate_count += 1
                issues.append(
                    ValidationIssue(
                        "duplicate_content",
                        f"Exact body duplicate of {duplicate_of} was excluded",
                        chunk.source_key,
                        fatal=False,
                    )
                )
                continue
            source_keys.add(chunk.source_key)
            if body_hash:
                body_hash_to_source[body_hash] = chunk.source_key
            valid.append(chunk)

        covered_page_ids = {chunk.wiki_page_id for chunk in valid}
        for page_id in sorted(expected_page_ids - covered_page_ids):
            issues.append(
                ValidationIssue(
                    "page_without_chunks",
                    f"Page {page_id} produced no unique valid chunks",
                )
            )
        completeness = complete_count / len(candidates) if candidates else 0.0
        fatal_issues = [issue for issue in issues if issue.fatal]
        passed = bool(valid) and completeness >= 0.95 and not fatal_issues
        return ValidationReport(
            passed=passed,
            total_candidates=len(candidates),
            valid_chunk_count=len(valid),
            duplicate_count=duplicate_count,
            empty_count=empty_count,
            metadata_complete_count=complete_count,
            metadata_completeness=round(completeness, 4),
            expected_page_count=len(expected_page_ids),
            covered_page_count=len(covered_page_ids),
            issues=tuple(issues),
            valid_chunks=tuple(valid),
        )

    @staticmethod
    def _missing_metadata(chunk: ChunkDraft) -> list[str]:
        required: dict[str, object] = {
            "page_title": chunk.page_title,
            "section_path": chunk.section_path,
            "canonical_url": chunk.canonical_url,
            "revision_id": chunk.revision_id,
            "game_scope": chunk.game_scope,
            "source_key": chunk.source_key,
            "content_hash": chunk.content_hash,
            "token_count": chunk.token_count,
        }
        return [name for name, value in required.items() if value in {None, "", 0}]
