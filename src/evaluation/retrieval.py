"""Small milestone retrieval benchmark and acceptance metrics."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.retrieval import RetrievalService

DEFAULT_RETRIEVAL_DATASET = Path("data/evaluation/retrieval_milestone6.json")
EvaluationCategory = Literal["entity", "natural"]


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationCase:
    """One query and the acceptable page titles for retrieval recall."""

    id: str
    category: EvaluationCategory
    query: str
    expected_titles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationDataset:
    """Version-controlled cases and milestone acceptance targets."""

    cases: tuple[RetrievalEvaluationCase, ...]
    target_entity_recall_at_5: float
    target_natural_recall_at_10: float
    target_p95_retrieval_ms: float

    @classmethod
    def load(cls, path: Path = DEFAULT_RETRIEVAL_DATASET) -> RetrievalEvaluationDataset:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
            raise ValueError("Retrieval evaluation dataset is malformed")
        cases: list[RetrievalEvaluationCase] = []
        for raw_case in payload["cases"]:
            if not isinstance(raw_case, dict):
                raise ValueError("Retrieval evaluation case is not an object")
            category = str(raw_case.get("category"))
            if category not in {"entity", "natural"}:
                raise ValueError(f"Unsupported retrieval evaluation category: {category}")
            raw_titles = raw_case.get("expected_titles")
            if not isinstance(raw_titles, list) or not raw_titles:
                raise ValueError("Retrieval evaluation case has no expected titles")
            cases.append(
                RetrievalEvaluationCase(
                    id=str(raw_case["id"]),
                    category=category,  # type: ignore[arg-type]
                    query=str(raw_case["query"]),
                    expected_titles=tuple(str(title) for title in raw_titles),
                )
            )
        return cls(
            cases=tuple(cases),
            target_entity_recall_at_5=float(payload["target_entity_recall_at_5"]),
            target_natural_recall_at_10=float(payload["target_natural_recall_at_10"]),
            target_p95_retrieval_ms=float(payload["target_p95_retrieval_ms"]),
        )


@dataclass(frozen=True, slots=True)
class RetrievalCaseResult:
    """Observed rank/scope/latency for one evaluation query."""

    id: str
    category: EvaluationCategory
    expected_titles: tuple[str, ...]
    returned_titles: tuple[str, ...]
    hit_rank: int | None
    scope_violation: bool
    retrieval_latency_ms: float

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "category": self.category,
            "expected_titles": list(self.expected_titles),
            "returned_titles": list(self.returned_titles),
            "hit_rank": self.hit_rank,
            "scope_violation": self.scope_violation,
            "retrieval_latency_ms": round(self.retrieval_latency_ms, 3),
        }


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationReport:
    """Aggregate recall, scope, and local Supabase latency acceptance report."""

    passed: bool
    entity_recall_at_5: float
    natural_recall_at_10: float
    p95_retrieval_ms: float
    scope_violation_count: int
    cases: tuple[RetrievalCaseResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "entity_recall_at_5": self.entity_recall_at_5,
            "natural_recall_at_10": self.natural_recall_at_10,
            "p95_retrieval_ms": round(self.p95_retrieval_ms, 3),
            "scope_violation_count": self.scope_violation_count,
            "cases": [case.to_dict() for case in self.cases],
        }


class RetrievalEvaluator:
    """Evaluate the retrieval service against the milestone dataset."""

    def __init__(self, service: RetrievalService) -> None:
        self.service = service

    def evaluate(self, dataset: RetrievalEvaluationDataset) -> RetrievalEvaluationReport:
        """Compute entity/natural recall, strict scope, and nearest-rank p95 latency."""
        case_results: list[RetrievalCaseResult] = []
        for case in dataset.cases:
            result = self.service.retrieve(case.query, match_count=10)
            returned_titles = tuple(candidate.page_title for candidate in result.candidates)
            expected = {title.casefold() for title in case.expected_titles}
            hit_rank = next(
                (
                    index
                    for index, title in enumerate(returned_titles, start=1)
                    if title.casefold() in expected
                ),
                None,
            )
            case_results.append(
                RetrievalCaseResult(
                    id=case.id,
                    category=case.category,
                    expected_titles=case.expected_titles,
                    returned_titles=returned_titles,
                    hit_rank=hit_rank,
                    scope_violation=any(
                        candidate.game_scope != "dst" for candidate in result.candidates
                    ),
                    retrieval_latency_ms=result.retrieval_latency_ms,
                )
            )
        entity_cases = [case for case in case_results if case.category == "entity"]
        natural_cases = [case for case in case_results if case.category == "natural"]
        entity_recall = self._recall(entity_cases, cutoff=5)
        natural_recall = self._recall(natural_cases, cutoff=10)
        scope_violations = sum(case.scope_violation for case in case_results)
        p95 = self._percentile(
            [case.retrieval_latency_ms for case in case_results],
            percentile=0.95,
        )
        passed = (
            entity_recall >= dataset.target_entity_recall_at_5
            and natural_recall >= dataset.target_natural_recall_at_10
            and scope_violations == 0
            and p95 <= dataset.target_p95_retrieval_ms
        )
        return RetrievalEvaluationReport(
            passed=passed,
            entity_recall_at_5=entity_recall,
            natural_recall_at_10=natural_recall,
            p95_retrieval_ms=p95,
            scope_violation_count=scope_violations,
            cases=tuple(case_results),
        )

    @staticmethod
    def _recall(cases: list[RetrievalCaseResult], *, cutoff: int) -> float:
        if not cases:
            return 0.0
        return sum(case.hit_rank is not None and case.hit_rank <= cutoff for case in cases) / len(
            cases
        )

    @staticmethod
    def _percentile(values: list[float], *, percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = max(0, math.ceil(percentile * len(ordered)) - 1)
        return ordered[index]
