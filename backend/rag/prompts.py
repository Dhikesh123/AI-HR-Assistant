"""Prompt templates.

All prompt text lives here rather than inside route or service functions so it
can be reviewed, versioned and tuned independently of application logic.
"""
from __future__ import annotations

from typing import Iterable, List, Sequence

from backend.core.config import settings

# Exact wording the assistant must use when the answer is not in the documents.
NO_ANSWER_RESPONSE = (
    "I could not find this information in the available HR documents. "
    "Please contact the HR department for clarification."
)

SYSTEM_PROMPT = """You are an AI HR Assistant for {company}.

Your job is to answer employee HR questions using the company HR documents.

Follow these rules:

1. Answer using only the provided HR context.
2. Do not invent information, numbers, dates or policy names.
3. If the answer is not available in the context, reply with exactly:
   "{no_answer}"
4. Keep the response clear, concise and professional.
5. Do not reveal confidential employee information.
6. Refer to the source document by name when it helps the employee.
7. If the context only partially answers the question, answer the part you can
   and say plainly which part is not covered by the documents.
"""

USER_PROMPT = """HR Context:
{context}

{history_block}Employee Question:
{question}

Answer:"""

HISTORY_BLOCK = """Recent conversation (for follow-up questions):
{history}

"""

CONTEXT_ITEM = """[Source {index}] {document} (page {page}, section: {section})
{text}"""

# Rewrites a follow-up such as "Can I carry them forward?" into a standalone
# query so retrieval does not lose the subject of the conversation.
QUERY_REWRITE_PROMPT = """Rewrite the employee's latest question into a single
standalone HR search query. Resolve pronouns using the conversation. Reply with
the rewritten query only, no preamble.

Conversation:
{history}

Latest question: {question}

Standalone query:"""


def build_system_prompt(company: str | None = None) -> str:
    """Render the system prompt for the configured company."""
    return SYSTEM_PROMPT.format(
        company=company or settings.COMPANY_NAME,
        no_answer=NO_ANSWER_RESPONSE,
    )


def format_context(chunks: Sequence) -> str:
    """Render retrieved chunks into the numbered context block."""
    parts: List[str] = []
    for index, chunk in enumerate(chunks, start=1):
        parts.append(
            CONTEXT_ITEM.format(
                index=index,
                document=chunk.metadata.get("document_name", "unknown"),
                page=chunk.metadata.get("page_number", "n/a"),
                section=chunk.metadata.get("section", "General"),
                text=chunk.text.strip(),
            )
        )
    return "\n\n".join(parts) if parts else "(no relevant HR context was found)"


def format_history(history: Iterable[tuple[str, str]]) -> str:
    """Render prior turns as ``Employee:`` / ``Assistant:`` lines."""
    lines = [
        f"{'Employee' if role == 'user' else 'Assistant'}: {content.strip()}"
        for role, content in history
    ]
    return "\n".join(lines)


def build_user_prompt(
    question: str,
    chunks: Sequence,
    history: Iterable[tuple[str, str]] | None = None,
) -> str:
    """Render the full user prompt including context and optional history."""
    history_text = format_history(history or [])
    history_block = HISTORY_BLOCK.format(history=history_text) if history_text else ""
    return USER_PROMPT.format(
        context=format_context(chunks),
        history_block=history_block,
        question=question.strip(),
    )


def build_query_rewrite_prompt(question: str, history: Iterable[tuple[str, str]]) -> str:
    """Render the follow-up question rewrite prompt."""
    return QUERY_REWRITE_PROMPT.format(
        history=format_history(history),
        question=question.strip(),
    )
