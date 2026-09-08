"""RAG pipeline tests: chunking, retrieval, grounding and citations."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.rag.chunker import create_chunks, detect_section, split_text
from backend.rag.loader import (
    UnsupportedFileTypeError,
    clean_text,
    load_document,
    strip_repeated_lines,
)
from backend.rag.prompts import NO_ANSWER_RESPONSE, build_user_prompt, format_context
from backend.rag.text_utils import content_words, stem
from backend.services import rag_service

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_hr_documents"


# ----------------------------------------------------------------------
# Loading and cleaning
# ----------------------------------------------------------------------
def test_clean_text_rejoins_wrapped_lines_but_keeps_headings() -> None:
    raw = (
        "4. Leave Entitlement\n"
        "Every confirmed employee is entitled to 12 casual leaves per leave year and\n"
        "may take two consecutive days.\n"
    )
    cleaned = clean_text(raw)
    lines = cleaned.splitlines()
    assert lines[0] == "4. Leave Entitlement"
    assert "per leave year and may take" in lines[1]


def test_strip_repeated_lines_removes_running_footer() -> None:
    footer = "ACME Corporation - Internal HR document"
    pages = [(n, f"Page {n} body text.\n{footer}") for n in range(1, 6)]
    cleaned = strip_repeated_lines(pages)
    assert all(footer not in text for _, text in cleaned)
    assert all("body text" in text for _, text in cleaned)


def test_load_document_rejects_unsupported_type(tmp_path: Path) -> None:
    bad = tmp_path / "payroll.exe"
    bad.write_bytes(b"binary")
    with pytest.raises(UnsupportedFileTypeError):
        load_document(bad)


def test_load_pdf_returns_pages_with_numbers() -> None:
    pages = load_document(SAMPLE_DIR / "leave_policy.pdf")
    assert len(pages) >= 5
    assert [n for n, _ in pages] == sorted(n for n, _ in pages)
    assert any("Leave Entitlement" in text for _, text in pages)


# ----------------------------------------------------------------------
# Chunking
# ----------------------------------------------------------------------
def test_split_text_respects_chunk_size() -> None:
    text = "This is a sentence about company leave policy. " * 80
    chunks = split_text(text, chunk_size=300, chunk_overlap=50)
    assert len(chunks) > 1
    assert all(len(chunk) <= 450 for chunk in chunks)


def test_detect_section_finds_numbered_heading() -> None:
    assert detect_section("4. Leave Entitlement\nEvery employee gets 12 days.") == "Leave Entitlement"


def test_detect_section_ignores_prose_and_footers() -> None:
    footer = "ACME Corporation - Internal HR document - fictional sample data"
    assert detect_section(footer, fallback="General") == "General"
    assert detect_section("Employees may take leave.", fallback="General") == "General"


def test_create_chunks_attaches_citation_metadata() -> None:
    pages = [(4, "4. Leave Entitlement\nEmployees receive 12 casual leaves per year.")]
    chunks = create_chunks(pages, document_name="leave_policy.pdf", document_id=42)
    assert chunks
    metadata = chunks[0].metadata
    assert metadata["document_name"] == "leave_policy.pdf"
    assert metadata["page_number"] == 4
    assert metadata["document_id"] == 42
    assert metadata["section"] == "Leave Entitlement"


# ----------------------------------------------------------------------
# Text utilities
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("apply", "apply"),
        ("applied", "apply"),
        ("applies", "apply"),
        ("leaves", "leave"),
        ("leave", "leave"),
        ("carried", "carry"),
        ("business", "business"),
    ],
)
def test_stemmer_collapses_word_forms(word: str, expected: str) -> None:
    assert stem(word) == expected


def test_content_words_drop_stopwords() -> None:
    assert content_words("How many casual leaves do I get?") == {"casual", "leave"}


# ----------------------------------------------------------------------
# Prompts
# ----------------------------------------------------------------------
def test_prompt_includes_context_and_question(indexed_corpus: int) -> None:
    chunks = rag_service.retrieve_context("How many casual leaves do I get?")
    prompt = build_user_prompt("How many casual leaves do I get?", chunks)
    assert "HR Context:" in prompt
    assert "How many casual leaves do I get?" in prompt
    assert "[Source 1]" in prompt


def test_format_context_reports_missing_context() -> None:
    assert "no relevant HR context" in format_context([])


# ----------------------------------------------------------------------
# Retrieval and answering
# ----------------------------------------------------------------------
def test_corpus_is_indexed(indexed_corpus: int) -> None:
    assert indexed_corpus > 20


def test_retrieval_finds_the_right_document(indexed_corpus: int) -> None:
    chunks = rag_service.retrieve_context("How many casual leaves do I get?")
    assert chunks
    documents = {chunk.document_name for chunk in chunks}
    assert {"leave_policy.pdf", "hr_faq.pdf", "employee_handbook.pdf"} & documents


def test_retrieval_returns_top_k(indexed_corpus: int) -> None:
    chunks = rag_service.retrieve_context("What is the work from home policy?", top_k=2)
    assert len(chunks) <= 2


def test_authoritative_section_outranks_passing_mention(indexed_corpus: int) -> None:
    """The section that is *about* the question must beat one that name-drops it.

    Guards the section-title component of the re-ranker: leave_policy.pdf's
    "Leave Entitlement" page must place above pages that merely mention casual
    leave in passing.
    """
    chunks = rag_service.retrieve_context("How many casual leaves do I get?", top_k=4)
    sections = [(chunk.document_name, chunk.section) for chunk in chunks]
    assert ("leave_policy.pdf", "Leave Entitlement") in sections


def test_answer_contains_correct_fact(indexed_corpus: int) -> None:
    result = rag_service.answer_question("How many casual leaves do I get?")
    assert result.answered
    assert "12" in result.answer


def test_answer_returns_source_citations(indexed_corpus: int) -> None:
    result = rag_service.answer_question("How many sick leaves are available?")
    assert result.sources
    first = result.sources[0]
    assert first["document"].endswith(".pdf")
    assert first["page"] is not None


def test_no_hallucination_for_missing_information(indexed_corpus: int) -> None:
    result = rag_service.answer_question("What is the company's international travel allowance?")
    assert result.answer == NO_ANSWER_RESPONSE
    assert result.sources == []
    assert not result.answered


def test_no_hallucination_for_absurd_question(indexed_corpus: int) -> None:
    result = rag_service.answer_question("How many company yachts can I borrow?")
    assert result.answer == NO_ANSWER_RESPONSE
    assert not result.answered


def test_answer_is_grounded_in_retrieved_text(indexed_corpus: int) -> None:
    """Every sentence of an offline answer must come from the retrieved chunks."""
    result = rag_service.answer_question("What is the notice period?")
    assert result.answered
    corpus = " ".join(chunk.text.replace("\n", " ") for chunk in result.chunks)
    corpus = " ".join(corpus.split())
    body = result.answer.split("Based on the HR documents:")[-1].split("(Source:")[0]
    for sentence in body.split(". "):
        sentence = sentence.strip().rstrip(".")
        if len(sentence) > 30:
            assert sentence in corpus


def test_empty_question_is_rejected() -> None:
    with pytest.raises(ValueError):
        rag_service.answer_question("   ")


def test_followup_uses_conversation_context(indexed_corpus: int) -> None:
    history = [
        ("user", "How many casual leaves do I get?"),
        ("assistant", "Employees receive 12 casual leaves per leave year."),
    ]
    result = rag_service.answer_question("Can I carry them forward?", history=history)
    assert result.answered
    assert "leave_policy.pdf" in {source["document"] for source in result.sources}


def test_ingest_and_delete_round_trip(tmp_path: Path) -> None:
    document = tmp_path / "pet_policy.txt"
    document.write_text(
        "1. Office Pets\nEmployees may bring one registered dog to the office on Fridays.",
        encoding="utf-8",
    )

    before = rag_service.index_stats()["chunks"]
    rag_service.ingest_document(document, document_id=9001, document_name="pet_policy.txt")
    assert rag_service.index_stats()["chunks"] > before

    answer = rag_service.answer_question("Can employees bring a registered dog to the office?")
    assert "pet_policy.txt" in {source["document"] for source in answer.sources}

    removed = rag_service.delete_document_vectors(9001)
    assert removed >= 1
    assert rag_service.index_stats()["chunks"] == before
