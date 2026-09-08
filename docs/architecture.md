# Architecture

How the AI HR Assistant is put together, and why.

---

## 1. System overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Streamlit frontend                            │
│   login · employee chat · chat history · admin dashboard              │
│   (talks to the backend only over REST — never to the DB or LLM)      │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTPS + JWT bearer
┌───────────────────────────────▼──────────────────────────────────────┐
│                          FastAPI backend                              │
│                                                                       │
│  api/        thin routes: validate → call a service → shape response  │
│  ────────────────────────────────────────────────────────────────────│
│  services/   business logic: auth, chat, document, rag, llm           │
│  ────────────────────────────────────────────────────────────────────│
│  rag/        loader · chunker · embeddings · vector_store ·           │
│              retriever · prompts · text_utils                         │
│  ────────────────────────────────────────────────────────────────────│
│  models/     SQLAlchemy ORM        core/  config · security · logging │
└──────┬──────────────────────────────────────────────┬────────────────┘
       │                                              │
┌──────▼────────────┐                    ┌────────────▼────────────────┐
│  SQLite           │                    │  ChromaDB                    │
│  users            │                    │  hr_documents collection     │
│  documents        │                    │  chunk text + embedding +    │
│  conversations    │                    │  citation metadata           │
│  messages         │                    └──────────────────────────────┘
│  feedback         │                                  │
└───────────────────┘                    ┌────────────▼────────────────┐
                                         │  LLM provider (optional)     │
                                         │  OpenAI-compatible API       │
                                         └──────────────────────────────┘
```

**The layering rule:** a route may not embed text, build a prompt or touch the
vector store. It validates input, calls one service function, and shapes the
response. All RAG logic sits behind `services/rag_service.py`, which is the only
module the API layer knows about for question answering.

---

## 2. Ingestion pipeline

```
 PDF / DOCX / TXT / MD
          │
          ▼
 ┌──────────────────┐   pypdf · python-docx · plain text
 │ loader.py        │   → [(page_number, text), …]
 └────────┬─────────┘
          │
          ▼
 ┌──────────────────┐   • rejoin PDF hard-wraps, keep headings on their own line
 │ clean_text       │   • strip running headers/footers repeated across pages
 └────────┬─────────┘
          │
          ▼
 ┌──────────────────┐   LangChain RecursiveCharacterTextSplitter
 │ chunker.py       │   (local equivalent if LangChain is absent)
 │                  │   CHUNK_SIZE=900, CHUNK_OVERLAP=150
 │                  │   + section detection per chunk
 └────────┬─────────┘
          │
          ▼
 ┌──────────────────┐   openai · sentence-transformers · local hashed
 │ embeddings.py    │
 └────────┬─────────┘
          │
          ▼
 ┌──────────────────┐   ids + documents + metadata + vectors
 │ vector_store.py  │   ChromaDB (cosine), or JSON fallback store
 └──────────────────┘
```

### Why clean before chunking

Raw PDF text extraction produces two problems that quietly wreck retrieval:

1. **Hard-wrapped lines.** A sentence broken across three lines becomes three
   fragments. `clean_text` rejoins a line into the next when the line is long and
   does not end in sentence punctuation, but leaves short lines alone — because a
   short line is almost always a heading, and headings are what section metadata
   is built from.

2. **Running headers and footers.** A footer on every page adds no information,
   dilutes the embedding of every chunk, and can be mistaken for a section
   heading. `strip_repeated_lines` drops any line that appears on 60%+ of pages.

Both were found by inspecting real output during development: before the fix,
section metadata read `"General"` or `"ACME Corporation - Internal HR document"`
instead of `"Leave Entitlement"`.

### Chunk metadata

Every chunk stores what a citation needs:

```json
{
  "document_name": "leave_policy.pdf",
  "document_id": 3,
  "page_number": 4,
  "section": "Leave Entitlement",
  "chunk_index": 12
}
```

`document_id` links back to the SQL `documents` row, which is what makes
delete-and-reindex exact: removing a document deletes precisely its vectors,
never a neighbour's.

---

## 3. Query pipeline

```
 Employee question
          │
          ▼
 ┌────────────────────────┐  Follow-ups only. With an LLM: rewrite into a
 │ rewrite_followup       │  standalone query. Offline: prepend the previous
 └───────────┬────────────┘  question. Resolves "Can I carry them forward?"
             │
             ▼
 ┌────────────────────────┐
 │ embed query            │
 └───────────┬────────────┘
             │
             ▼
 ┌────────────────────────┐  over-fetch TOP_K × 3 candidates
 │ vector search          │
 └───────────┬────────────┘
             │
             ▼
 ┌────────────────────────┐  score = 0.65 × cosine + 0.25 × keyword overlap
 │ rerank + threshold     │          + 0.10 × section-title match,
 │                        │          then drop < MIN_RELEVANCE_SCORE
 └───────────┬────────────┘
             │
        ┌────┴─────┐
   no chunks    chunks
        │           │
        ▼           ▼
   "could not   ┌────────────────────┐  system + context + history + question
    find …"     │ build prompt       │
                └─────────┬──────────┘
                          ▼
                ┌────────────────────┐  LLM, or extractive fallback
                │ generate answer    │
                └─────────┬──────────┘
                          ▼
                ┌────────────────────┐  deduplicated by (document, page)
                │ build sources      │
                └─────────┬──────────┘
                          ▼
                   answer + sources
```

### Why hybrid re-ranking

Pure vector similarity returns *topically* similar chunks. For HR questions the
answer usually hinges on a specific term — "casual", "gratuity", "probation" —
and a chunk that discusses leave generally can out-score the one that states the
entitlement. Blending in stemmed keyword overlap pulls the exact-term chunk up.

The section-title term exists for a failure seen in practice: for *"How many
casual leaves do I get?"*, the FAQ's **Attendance Questions** page out-ranked
`leave_policy.pdf` **Leave Entitlement** — because it mentions casual leave in
passing while discussing late arrivals. Scoring the section heading against the
question moves the authoritative section from 6th place into the top 3. Cheap
signal, and it favours the section that is *about* the question over one that
merely mentions it.

The stemmer (`rag/text_utils.py`) is deliberately crude but *consistent*: it must
map `apply`, `applied` and `applies` to the same stem, and `leave`/`leaves` to
the same stem, or overlap scoring silently misses correct answers. The rule order
matters — an early version stemmed `apply → app` and `applied → appl`, which made
"How do I apply for leave?" unanswerable.

---

## 4. How "I don't know" is enforced

Three independent guards, so a failure in one does not produce a fabricated
answer:

1. **Relevance floor.** Chunks scoring below `MIN_RELEVANCE_SCORE` are discarded.
   With nothing left, `generate_answer` returns the refusal without ever calling
   the LLM. No context, no answer.

2. **Prompt instruction.** The system prompt states the rules and gives the exact
   refusal string to use when the context does not contain the answer.

3. **Extractive-mode overlap gate.** Without an API key, a sentence is only
   quoted if it covers ≥ 60% of the question's meaningful words. A loosely
   related sentence cannot become an answer.

`rag_service.is_unanswered()` then classifies the final answer, and the flag is
persisted on the message. That is what powers the **Content gaps** view: the list
of questions employees asked that the documents could not answer is a concrete,
prioritised backlog for the HR team.

---

## 5. Pluggable backends

Three components are swappable behind a common interface, chosen at runtime.
This is what makes the project runnable on a machine with no API key and no
model downloads, while still using the production-grade path when configured.

| Component | Options | Selection |
| --- | --- | --- |
| Embeddings | OpenAI → sentence-transformers → local hashed | `EMBEDDING_PROVIDER`, `auto` picks best available |
| Vector store | ChromaDB → local JSON store | ChromaDB if importable, else fallback |
| Answering | LLM API → extractive | LLM if `OPENAI_API_KEY` is set |

Each falls back rather than crashing, and `/health` always reports which is
active, so a degraded mode is never silent.

**The trade-off:** the fallbacks are lexical, not semantic. Local embeddings
match wording rather than meaning, and extractive answers read like stitched
policy sentences. Retrieval, citations and refusal behaviour are unaffected —
only fluency and paraphrase-matching degrade.

---

## 6. Data model

```
users                        documents
├── id                       ├── id
├── name                     ├── filename
├── email          (unique)  ├── file_path
├── password_hash            ├── file_type / file_size
├── role  employee|admin     ├── uploaded_by ──► users.id
└── created_at               ├── status  processing|indexed|failed
     │                       ├── chunk_count / error_message
     │                       └── created_at / updated_at
     │                              │
     │                              └──► ChromaDB metadata.document_id
     ▼
conversations                messages                    feedback
├── id                       ├── id                      ├── id
├── user_id ──► users.id     ├── conversation_id ──►     ├── user_id
├── title                    ├── role  user|assistant    ├── conversation_id
├── created_at               ├── content                 ├── message_id ──►
└── updated_at               ├── sources_json            ├── rating  ±
                             ├── answered  (bool)        ├── comment
                             ├── latency_ms              └── created_at
                             └── created_at
```

Notes:

- `messages.sources_json` stores the citations *as returned at answer time*, so
  chat history stays accurate even after a document is deleted or re-indexed.
- `messages.answered` and `latency_ms` are written at answer time; the analytics
  endpoint aggregates them rather than recomputing anything.
- `feedback` is unique per `(user, message)` in practice — re-rating updates the
  existing row instead of inserting a duplicate.
- SQLite by default. Everything goes through SQLAlchemy with no SQLite-specific
  SQL, so moving to Postgres is a `DATABASE_URL` change.

---

## 7. Request lifecycle: `POST /api/chat`

```
1  HTTPBearer extracts the token                       core/dependencies.py
2  JWT decoded and verified, user loaded               core/security.py
3  Pydantic validates the body (empty question → 422)  schemas/chat.py
4  Route calls chat_service.ask(...)                   api/chat.py
5  Conversation created or ownership-checked           services/chat_service.py
6  User message persisted
7  Recent turns assembled as history
8  rag_service.answer_question(question, history)      services/rag_service.py
     ├── rewrite_followup
     ├── retrieve_context  → embed → search → rerank
     ├── generate_answer   → LLM or extractive
     └── build_sources
9  Assistant message persisted with sources + answered + latency
10 Response shaped by ChatResponse                     schemas/chat.py
```

Errors map to HTTP status rather than leaking internals: `401` unauthenticated,
`403` wrong role, `404` missing or not-yours, `422` invalid input, `503`
embedding or vector store unavailable, `500` generic (details go to the log only).

---

## 8. Design decisions and trade-offs

**Services own logic, routes stay thin.** Every route is a validate-delegate-shape
sandwich. The RAG pipeline is fully testable without HTTP, which is why
`test_rag.py` and the evaluation harness call `rag_service` directly.

**Synchronous indexing.** Uploading blocks until the document is indexed, so the
admin sees the real result immediately. For a demo-sized corpus this takes well
under a second. At enterprise scale this becomes a background job — the
`documents.status` column already models `processing | indexed | failed` for
exactly that migration.

**Chunk size 900 / overlap 150.** HR policy clauses are short and self-contained.
Larger chunks dilute the embedding with unrelated clauses; smaller ones split an
entitlement away from its qualifying sentence. The overlap keeps a clause whole
when it straddles a boundary.

**Citations deduplicated by (document, page).** Two chunks from the same page are
one citation to a reader.

**404 rather than 403 for another user's conversation.** A `403` confirms the
conversation exists, which leaks information; `404` does not.

**Sources persisted as JSON on the message.** Chat history shows what the
employee actually saw, even if the underlying document later changes.

---

## 9. Scaling path

| Concern | Now | Next step |
| --- | --- | --- |
| Database | SQLite | Postgres — change `DATABASE_URL` |
| Indexing | Synchronous in-request | Celery/RQ worker; `status` column already exists |
| Vector store | Embedded ChromaDB | Chroma server, pgvector or a managed store |
| Auth | JWT with local users | SSO / OIDC against the corporate IdP |
| Access control | Role-based (employee/admin) | Per-document ACLs by department |
| Observability | File + stdout logging | Structured logs, tracing, metrics on retrieval quality |
| Evaluation | 16-question offline suite | Continuous eval on real logged questions |

The pieces most likely to need replacing — embeddings, vector store, LLM — are
already behind interfaces with more than one implementation each, so swapping one
is a new class and a config value, not a rewrite.
