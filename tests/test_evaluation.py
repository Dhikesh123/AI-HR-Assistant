"""RAG evaluation harness.

Scores the pipeline on five dimensions using ``evaluation_questions.json``:

* retrieval relevance   - was the right document retrieved?
* answer correctness    - does the answer contain the expected facts?
* groundedness          - is every cited source actually a retrieved chunk?
* missing-answer handling - does an unanswerable question get refused?
* latency               - how long does a question take end to end?

Run it directly for a printed report::

    python -m tests.test_evaluation
"""
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.rag.prompts import NO_ANSWER_RESPONSE
from backend.services import rag_service

DATASET_PATH = Path(__file__).resolve().parent / "evaluation_questions.json"

# Thresholds the pipeline must clear for the suite to pass. They are deliberately
# achievable with the offline (no API key) backend; an LLM backend scores higher.
MIN_RETRIEVAL_RECALL = 0.85
MIN_ANSWER_CORRECTNESS = 0.70
MIN_REFUSAL_RATE = 1.00
MAX_MEAN_LATENCY_MS = 5000


def load_dataset() -> List[Dict[str, Any]]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


@dataclass
class EvaluationReport:
    """Aggregated metrics over the evaluation dataset."""

    retrieval_hits: int = 0
    retrieval_total: int = 0
    correct_answers: int = 0
    answerable_total: int = 0
    grounded: int = 0
    grounded_total: int = 0
    correct_refusals: int = 0
    unanswerable_total: int = 0
    latencies: List[int] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)

    @property
    def retrieval_recall(self) -> float:
        return self.retrieval_hits / self.retrieval_total if self.retrieval_total else 0.0

    @property
    def answer_correctness(self) -> float:
        return self.correct_answers / self.answerable_total if self.answerable_total else 0.0

    @property
    def groundedness(self) -> float:
        return self.grounded / self.grounded_total if self.grounded_total else 1.0

    @property
    def refusal_rate(self) -> float:
        return self.correct_refusals / self.unanswerable_total if self.unanswerable_total else 1.0

    @property
    def mean_latency_ms(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0.0

    @property
    def p95_latency_ms(self) -> float:
        if not self.latencies:
            return 0.0
        ordered = sorted(self.latencies)
        return ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]

    def render(self) -> str:
        return "\n".join(
            [
                "",
                "=" * 62,
                "RAG EVALUATION REPORT",
                "=" * 62,
                f"Retrieval relevance      : {self.retrieval_recall:6.1%}  "
                f"({self.retrieval_hits}/{self.retrieval_total})",
                f"Answer correctness       : {self.answer_correctness:6.1%}  "
                f"({self.correct_answers}/{self.answerable_total})",
                f"Groundedness             : {self.groundedness:6.1%}  "
                f"({self.grounded}/{self.grounded_total})",
                f"Missing-answer handling  : {self.refusal_rate:6.1%}  "
                f"({self.correct_refusals}/{self.unanswerable_total})",
                f"Mean latency             : {self.mean_latency_ms:6.0f} ms",
                f"P95 latency              : {self.p95_latency_ms:6.0f} ms",
                "=" * 62,
                *(["FAILURES:", *(f"  - {failure}" for failure in self.failures)] if self.failures else []),
            ]
        )


def evaluate() -> EvaluationReport:
    """Run every evaluation case and aggregate the metrics."""
    report = EvaluationReport()

    for case in load_dataset():
        question = case["question"]
        result = rag_service.answer_question(question)
        report.latencies.append(result.latency_ms)

        if case["answerable"]:
            report.answerable_total += 1
            report.retrieval_total += 1
            report.grounded_total += 1

            retrieved = {chunk.document_name for chunk in result.chunks}
            if set(case["expected_documents"]) & retrieved:
                report.retrieval_hits += 1
            else:
                report.failures.append(f"retrieval miss: {question} -> {sorted(retrieved)}")

            answer = result.answer.lower()
            if all(keyword.lower() in answer for keyword in case["expected_keywords"]):
                report.correct_answers += 1
            else:
                report.failures.append(f"answer miss: {question} -> {result.answer[:90]!r}")

            # Groundedness: every cited document must be one that was retrieved.
            cited = {source["document"] for source in result.sources}
            if cited and cited <= retrieved:
                report.grounded += 1
            elif not cited:
                report.failures.append(f"no citation: {question}")
            else:
                report.failures.append(f"ungrounded citation: {question} -> {cited - retrieved}")
        else:
            report.unanswerable_total += 1
            if result.answer == NO_ANSWER_RESPONSE and not result.sources:
                report.correct_refusals += 1
            else:
                report.failures.append(f"hallucination risk: {question} -> {result.answer[:90]!r}")

    return report


# ----------------------------------------------------------------------
# pytest entry points
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def report(indexed_corpus: int) -> EvaluationReport:
    result = evaluate()
    print(result.render())
    return result


def test_retrieval_relevance(report: EvaluationReport) -> None:
    assert report.retrieval_recall >= MIN_RETRIEVAL_RECALL, report.render()


def test_answer_correctness(report: EvaluationReport) -> None:
    assert report.answer_correctness >= MIN_ANSWER_CORRECTNESS, report.render()


def test_groundedness(report: EvaluationReport) -> None:
    """No answer may cite a document that retrieval did not return."""
    assert report.groundedness >= 1.0, report.render()


def test_missing_answer_handling(report: EvaluationReport) -> None:
    """Unanswerable questions must be refused, never guessed."""
    assert report.refusal_rate >= MIN_REFUSAL_RATE, report.render()


def test_latency(report: EvaluationReport) -> None:
    assert report.mean_latency_ms <= MAX_MEAN_LATENCY_MS, report.render()


if __name__ == "__main__":  # pragma: no cover - manual run
    print(evaluate().render())
