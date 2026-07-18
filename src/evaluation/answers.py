"""Deterministic citation, faithfulness, abstention, and subjectivity metrics."""

from __future__ import annotations

import re
from dataclasses import dataclass
from json import JSONDecodeError, loads
from pathlib import Path

from src.evaluation.release import ReleaseDataset
from src.generation.citations import CITATION_PATTERN, NUMBER_PATTERN
from src.terminology.normalizer import normalize_search_text


@dataclass(frozen=True, slots=True)
class AnswerCitationObservation:
    """Citation fields required for deterministic answer evaluation."""

    id: str
    page_title: str
    content: str


@dataclass(frozen=True, slots=True)
class AnswerObservation:
    """One generated response paired to a release question ID."""

    case_id: str
    answer: str
    citations: tuple[AnswerCitationObservation, ...]
    resolved_entity_titles: tuple[str, ...]
    abstained: bool
    subjective_warning: bool


@dataclass(frozen=True, slots=True)
class AnswerEvaluationReport:
    """Aggregate deterministic answer-quality metrics."""

    observation_count: int
    citation_correctness: float
    citation_completeness: float
    faithfulness: float
    answer_relevance: float
    numerical_accuracy: float
    abstention_precision: float
    abstention_recall: float
    subjectivity_labeling: float

    def to_dict(self) -> dict[str, object]:
        return {
            "observation_count": self.observation_count,
            "citation_correctness": round(self.citation_correctness, 4),
            "citation_completeness": round(self.citation_completeness, 4),
            "faithfulness": round(self.faithfulness, 4),
            "answer_relevance": round(self.answer_relevance, 4),
            "numerical_accuracy": round(self.numerical_accuracy, 4),
            "abstention_precision": round(self.abstention_precision, 4),
            "abstention_recall": round(self.abstention_recall, 4),
            "subjectivity_labeling": round(self.subjectivity_labeling, 4),
        }


class AnswerEvaluator:
    """Score saved responses without using another LLM as an unverified judge."""

    def evaluate(
        self,
        dataset: ReleaseDataset,
        observations: tuple[AnswerObservation, ...],
    ) -> AnswerEvaluationReport:
        if not observations:
            raise ValueError("Answer evaluation requires at least one observation")
        questions = {case.id: case for case in dataset.cases}
        if any(observation.case_id not in questions for observation in observations):
            raise ValueError("Answer observation references an unknown release case")
        citation_valid: list[bool] = []
        claim_coverage: list[float] = []
        faithful: list[bool] = []
        relevance: list[bool] = []
        numeric_valid: list[bool] = []
        expected_abstentions = 0
        predicted_abstentions = 0
        true_abstentions = 0
        subjective_results: list[bool] = []
        for observation in observations:
            question = questions[observation.case_id]
            if question.expected_behavior == "abstain":
                expected_abstentions += 1
            if observation.abstained:
                predicted_abstentions += 1
                if question.expected_behavior == "abstain":
                    true_abstentions += 1
                continue
            source_map = {citation.id: citation for citation in observation.citations}
            cited_ids = CITATION_PATTERN.findall(observation.answer)
            structural = bool(cited_ids) and set(cited_ids).issubset(source_map)
            citation_valid.append(structural)
            coverage = self._claim_coverage(observation.answer)
            claim_coverage.append(coverage)
            numbers_supported = self._numbers_supported(observation.answer, source_map)
            numeric_valid.append(numbers_supported)
            faithful.append(structural and coverage == 1.0 and numbers_supported)
            expected = {title.casefold() for title in question.expected_titles}
            observed_titles = {
                citation.page_title.casefold() for citation in observation.citations
            } | {title.casefold() for title in observation.resolved_entity_titles}
            relevance.append(bool(expected & observed_titles))
            if "subjective" in question.tags:
                subjective_results.append(observation.subjective_warning)
        return AnswerEvaluationReport(
            observation_count=len(observations),
            citation_correctness=self._mean(citation_valid),
            citation_completeness=self._mean(claim_coverage),
            faithfulness=self._mean(faithful),
            answer_relevance=self._mean(relevance),
            numerical_accuracy=self._mean(numeric_valid),
            abstention_precision=(
                true_abstentions / predicted_abstentions if predicted_abstentions else 0.0
            ),
            abstention_recall=(
                true_abstentions / expected_abstentions if expected_abstentions else 0.0
            ),
            subjectivity_labeling=self._mean(subjective_results),
        )

    @staticmethod
    def _claim_coverage(answer: str) -> float:
        claims = [
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+|\n+", answer)
            if len(normalize_search_text(part).split()) >= 4
        ]
        if not claims:
            return 0.0
        return sum(bool(CITATION_PATTERN.search(claim)) for claim in claims) / len(claims)

    @staticmethod
    def _numbers_supported(
        answer: str,
        source_map: dict[str, AnswerCitationObservation],
    ) -> bool:
        for claim in re.split(r"(?<=[.!?])\s+|\n+", answer):
            numbers = {value.replace(",", ".") for value in NUMBER_PATTERN.findall(claim)}
            if not numbers:
                continue
            cited_ids = CITATION_PATTERN.findall(claim)
            evidence = " ".join(
                source_map[source_id].content for source_id in cited_ids if source_id in source_map
            )
            evidence_numbers = {
                value.replace(",", ".") for value in NUMBER_PATTERN.findall(evidence)
            }
            if not numbers.issubset(evidence_numbers):
                return False
        return True

    @staticmethod
    def _mean(values: list[bool] | list[float]) -> float:
        return sum(values) / len(values) if values else 0.0


def load_answer_observations(path: Path) -> tuple[AnswerObservation, ...]:
    """Load explicit saved responses without generating or silently filling observations."""
    try:
        payload = loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, JSONDecodeError) as exc:
        raise ValueError(f"Could not read answer observations from {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Unsupported answer observation schema")
    raw_observations = payload.get("observations")
    if not isinstance(raw_observations, list) or not raw_observations:
        raise ValueError("Answer observations must be a non-empty list")

    observations: list[AnswerObservation] = []
    seen_ids: set[str] = set()
    for raw in raw_observations:
        if not isinstance(raw, dict):
            raise ValueError("Answer observation is not an object")
        case_id = str(raw.get("case_id", ""))
        if not case_id or case_id in seen_ids:
            raise ValueError(f"Duplicate or empty answer observation ID: {case_id}")
        seen_ids.add(case_id)
        raw_citations = raw.get("citations")
        raw_titles = raw.get("resolved_entity_titles")
        answer = raw.get("answer")
        abstained = raw.get("abstained")
        subjective_warning = raw.get("subjective_warning")
        if (
            not isinstance(raw_citations, list)
            or not isinstance(raw_titles, list)
            or not isinstance(answer, str)
            or not isinstance(abstained, bool)
            or not isinstance(subjective_warning, bool)
        ):
            raise ValueError(f"Answer observation {case_id} has malformed lists")
        citations: list[AnswerCitationObservation] = []
        for citation in raw_citations:
            if not isinstance(citation, dict):
                raise ValueError(f"Answer observation {case_id} has a malformed citation")
            citations.append(
                AnswerCitationObservation(
                    id=str(citation.get("id", "")),
                    page_title=str(citation.get("page_title", "")),
                    content=str(citation.get("content", "")),
                )
            )
        observations.append(
            AnswerObservation(
                case_id=case_id,
                answer=answer,
                citations=tuple(citations),
                resolved_entity_titles=tuple(str(title) for title in raw_titles),
                abstained=abstained,
                subjective_warning=subjective_warning,
            )
        )
    return tuple(observations)
