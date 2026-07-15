"""Release evaluation dataset validation and ranking metrics."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.retrieval import RetrievalService

DEFAULT_RELEASE_DATASET = Path("data/evaluation/release_questions.json")
ReleaseCategory = Literal[
    "entity_lookup",
    "crafting_acquisition",
    "mechanic",
    "character",
    "comparison",
    "strategy_recommendation",
    "typo_non_accented",
    "out_of_scope",
]
ExpectedBehavior = Literal["answer", "abstain"]
VALID_CATEGORIES = {
    "entity_lookup",
    "crafting_acquisition",
    "mechanic",
    "character",
    "comparison",
    "strategy_recommendation",
    "typo_non_accented",
    "out_of_scope",
}


@dataclass(frozen=True, slots=True)
class ReleaseQuestion:
    """One version-controlled release evaluation question."""

    id: str
    category: ReleaseCategory
    query: str
    expected_titles: tuple[str, ...]
    expected_behavior: ExpectedBehavior
    tags: tuple[str, ...]
    benchmark_ready: bool


@dataclass(frozen=True, slots=True)
class ReleaseDataset:
    """Validated 150+ question coverage set and executable benchmark subset."""

    cases: tuple[ReleaseQuestion, ...]
    minimum_category_counts: dict[str, int]

    @classmethod
    def load(cls, path: Path = DEFAULT_RELEASE_DATASET) -> ReleaseDataset:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("Unsupported release evaluation schema")
        raw_counts = payload.get("minimum_category_counts")
        raw_cases = payload.get("cases")
        if not isinstance(raw_counts, dict) or not isinstance(raw_cases, list):
            raise ValueError("Release evaluation dataset is malformed")
        minimum_counts = {str(key): int(value) for key, value in raw_counts.items()}
        cases: list[ReleaseQuestion] = []
        seen_ids: set[str] = set()
        for raw in raw_cases:
            if not isinstance(raw, dict):
                raise ValueError("Release evaluation case is not an object")
            identifier = str(raw.get("id", ""))
            if not identifier or identifier in seen_ids:
                raise ValueError(f"Duplicate or empty release evaluation ID: {identifier}")
            seen_ids.add(identifier)
            category = str(raw.get("category"))
            behavior = str(raw.get("expected_behavior"))
            titles = raw.get("expected_titles")
            tags = raw.get("tags")
            if category not in VALID_CATEGORIES:
                raise ValueError(f"Unsupported release category: {category}")
            if behavior not in {"answer", "abstain"}:
                raise ValueError(f"Unsupported expected behavior: {behavior}")
            if not isinstance(titles, list) or not isinstance(tags, list):
                raise ValueError(f"Release case {identifier} has malformed lists")
            if behavior == "answer" and not titles:
                raise ValueError(f"Answer case {identifier} has no expected title")
            if behavior == "abstain" and titles:
                raise ValueError(f"Abstention case {identifier} must not expect titles")
            cases.append(
                ReleaseQuestion(
                    id=identifier,
                    category=category,  # type: ignore[arg-type]
                    query=str(raw.get("query", "")),
                    expected_titles=tuple(str(title) for title in titles),
                    expected_behavior=behavior,  # type: ignore[arg-type]
                    tags=tuple(str(tag) for tag in tags),
                    benchmark_ready=bool(raw.get("benchmark_ready", False)),
                )
            )
        observed: Counter[str] = Counter(case.category for case in cases)
        for category, minimum in minimum_counts.items():
            if observed[category] < minimum:
                raise ValueError(
                    f"Release category {category} has {observed[category]} cases; needs {minimum}"
                )
        if len(cases) < 150:
            raise ValueError("Release evaluation dataset must contain at least 150 questions")
        return cls(cases=tuple(cases), minimum_category_counts=minimum_counts)

    @property
    def benchmark_cases(self) -> tuple[ReleaseQuestion, ...]:
        return tuple(
            case
            for case in self.cases
            if case.benchmark_ready and case.expected_behavior == "answer"
        )

    @property
    def category_counts(self) -> dict[str, int]:
        return dict(Counter(case.category for case in self.cases))


@dataclass(frozen=True, slots=True)
class ReleaseRetrievalReport:
    """Full ranking, entity, scope, and latency metrics for executable cases."""

    passed: bool
    dataset_case_count: int
    benchmark_case_count: int
    recall_at_1: float
    recall_at_5: float
    recall_at_10: float
    mrr: float
    ndcg_at_10: float
    entity_resolution_accuracy: float
    dst_scope_accuracy: float
    latency_p50_ms: float
    latency_p95_ms: float

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "dataset_case_count": self.dataset_case_count,
            "benchmark_case_count": self.benchmark_case_count,
            "recall_at_1": round(self.recall_at_1, 4),
            "recall_at_5": round(self.recall_at_5, 4),
            "recall_at_10": round(self.recall_at_10, 4),
            "mrr": round(self.mrr, 4),
            "ndcg_at_10": round(self.ndcg_at_10, 4),
            "entity_resolution_accuracy": round(self.entity_resolution_accuracy, 4),
            "dst_scope_accuracy": round(self.dst_scope_accuracy, 4),
            "latency_p50_ms": round(self.latency_p50_ms, 3),
            "latency_p95_ms": round(self.latency_p95_ms, 3),
        }


class ReleaseRetrievalEvaluator:
    """Compute release metrics without pretending uncovered cases were executed."""

    def __init__(self, service: RetrievalService) -> None:
        self.service = service

    def evaluate(self, dataset: ReleaseDataset) -> ReleaseRetrievalReport:
        cases = dataset.benchmark_cases
        if not cases:
            raise ValueError("Release dataset has no benchmark-ready answer cases")
        ranks: list[int | None] = []
        ndcgs: list[float] = []
        entity_hits: list[bool] = []
        scope_hits: list[bool] = []
        latencies: list[float] = []
        for case in cases:
            result = self.service.retrieve(case.query, match_count=10)
            returned = [candidate.page_title.casefold() for candidate in result.candidates]
            expected = {title.casefold() for title in case.expected_titles}
            hit_rank = next(
                (index for index, title in enumerate(returned, start=1) if title in expected),
                None,
            )
            ranks.append(hit_rank)
            ndcgs.append(self._ndcg(returned, expected, cutoff=10))
            scope_hits.append(all(candidate.game_scope == "dst" for candidate in result.candidates))
            latencies.append(result.retrieval_latency_ms)
            if case.category == "entity_lookup":
                resolved = {
                    entity.entity_title.casefold() for entity in result.query.resolved_entities
                }
                entity_hits.append(bool(resolved & expected))
        recall_1 = self._recall(ranks, 1)
        recall_5 = self._recall(ranks, 5)
        recall_10 = self._recall(ranks, 10)
        mrr = sum(1.0 / rank if rank is not None else 0.0 for rank in ranks) / len(ranks)
        ndcg = sum(ndcgs) / len(ndcgs)
        entity_accuracy = sum(entity_hits) / len(entity_hits) if entity_hits else 0.0
        scope_accuracy = sum(scope_hits) / len(scope_hits)
        p50 = self._percentile(latencies, 0.50)
        p95 = self._percentile(latencies, 0.95)
        passed = recall_5 >= 0.90 and recall_10 >= 0.85 and scope_accuracy >= 0.98 and p95 <= 1500.0
        return ReleaseRetrievalReport(
            passed=passed,
            dataset_case_count=len(dataset.cases),
            benchmark_case_count=len(cases),
            recall_at_1=recall_1,
            recall_at_5=recall_5,
            recall_at_10=recall_10,
            mrr=mrr,
            ndcg_at_10=ndcg,
            entity_resolution_accuracy=entity_accuracy,
            dst_scope_accuracy=scope_accuracy,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
        )

    @staticmethod
    def _recall(ranks: list[int | None], cutoff: int) -> float:
        return sum(rank is not None and rank <= cutoff for rank in ranks) / len(ranks)

    @staticmethod
    def _ndcg(returned: list[str], expected: set[str], *, cutoff: int) -> float:
        seen_relevant: set[str] = set()
        gains: list[float] = []
        for title in returned[:cutoff]:
            relevant = title in expected and title not in seen_relevant
            gains.append(1.0 if relevant else 0.0)
            if relevant:
                seen_relevant.add(title)
        dcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))
        ideal_hits = min(len(expected), cutoff)
        ideal = sum(1.0 / math.log2(index + 2) for index in range(ideal_hits))
        return dcg / ideal if ideal else 0.0

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        ordered = sorted(values)
        index = max(0, math.ceil(percentile * len(ordered)) - 1)
        return ordered[index]
