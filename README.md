# AI HR Assistant

An enterprise-style RAG application that lets employees ask HR questions and get
answers grounded in the company's own HR documents — with source citations,
role-based access, chat history, feedback and an admin dashboard.

Built with **FastAPI + Streamlit + ChromaDB + LangChain + SQLite**.

```
Employee question ──► embedding ──► ChromaDB ──► top-K chunks ──► prompt ──► LLM ──► answer + sources
```

---

## Table of contents

- [What it does](#what-it-does)
- [Quick start](#quick-start)
- [Running with Docker](#running-with-docker)
- [Demo script](#demo-script)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Running without an API key](#running-without-an-api-key)
- [API reference](#api-reference)
- [Project layout](#project-layout)
- [Testing and evaluation](#testing-and-evaluation)
- [RAG vs fine-tuning](#rag-vs-fine-tuning)
- [Security notes](#security-notes)
- [Troubleshooting](#troubleshooting)

---

## What it does

**Employees can**
- sign in and ask HR questions in natural language
- see the answer plus the exact document, page and section it came from
- ask follow-up questions that keep the conversation's context
- browse and reopen past conversations
- rate answers 👍 / 👎

**HR admins can**
- upload HR documents (PDF, DOCX, TXT, MD) and have them indexed automatically
- view, re-index and delete documents
- see what employees are asking
- see the **content gaps** — questions the documents could not answer
- track usage analytics and feedback

**The assistant will not make things up.** If the answer is not in the indexed
documents it replies:

> I could not find this information in the available HR documents. Please contact
> the HR department for clarification.

---

## Quick start

Requires Python 3.10+.

```bash
# 1. Install
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env               # Windows: copy .env.example .env

# 3. Create the fictional HR documents (10 sample policy PDFs)
python -m scripts.generate_sample_documents

# 4. Create the database, demo users, and index the documents
python -m backend.database.init_db

# 5. Run the API (terminal 1)
uvicorn backend.main:app --reload

# 6. Run the UI (terminal 2)
streamlit run frontend/app.py
```

Then open:

| Service | URL |
| --- | --- |
| Streamlit UI | http://localhost:8501 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

**Demo accounts** (created by step 4):

| Role | Email | Password |
| --- | --- | --- |
| HR Admin | `admin@acme.com` | `Admin@123` |
| Employee | `employee@acme.com` | `Employee@123` |

> Change these in `.env` before deploying anywhere real.

---

## Running with Docker

```bash
cp .env.example .env
docker compose up --build
```

- UI → http://localhost:8501
- API → http://localhost:8000/docs

The backend container runs `backend.database.init_db` on start, which creates the
schema, seeds the demo users and indexes everything in
`data/sample_hr_documents/`. Database, vector store and uploads persist in named
volumes, so `docker compose down` keeps your data (`down -v` clears it).

---

## Demo script

A five-minute walkthrough that shows the whole pipeline:

1. **Sign in as the employee** (`employee@acme.com`) and ask
   *"How many casual leaves do I get?"*
   → answer cites `leave_policy.pdf`, with the page and section.
2. **Ask a follow-up**: *"Can I carry them forward?"*
   → the answer resolves "them" to casual leave and cites the
   *Carry Forward and Encashment* section.
3. **Ask something not in the documents**: *"What is the company's international
   travel allowance?"*
   → the assistant refuses instead of guessing.
4. **Rate an answer** 👍 or 👎.
5. **Sign in as the admin** (`admin@acme.com`) → **Dashboard**.
   - Upload a new policy file (a `.txt` works fine for a live demo):
     ```
     1. International Travel
     Employees travelling internationally receive a daily allowance of USD 75.
     ```
   - Watch it index, then ask the travel question again as the employee — it is
     now answered and cited. **This is the RAG loop, live.**
6. Back on the dashboard, check **Recent questions**, **Content gaps** and
   **Feedback**.

---

## Architecture

```
                          AI HR ASSISTANT
                                 |
                 +---------------+---------------+
                 |                               |
              EMPLOYEE                        HR ADMIN
                 |                               |
            Ask question                   Upload document
                 |                               |
                 v                               v
         Query processing               Document processing
                 |                               |
                 v                               v
           Query embedding                 Text extraction
                 |                               |
                 v                               v
          Vector search (ChromaDB)          Cleaning + chunking
                 |                               |
                 v                               v
          Top-K relevant chunks              Embeddings
                 |                               |
                 +---------------+---------------+
                                 |
                                 v
                          Prompt template
                                 |
                                 v
                                LLM
                                 |
                                 v
                          Final AI response
                                 |
                        +--------+--------+
                        |                 |
                     Answer            Sources
```

**Ingestion** — `PDF/DOCX/TXT → loader → clean → chunk → embed → ChromaDB`.
Each chunk carries citation metadata:

```json
{
  "document_name": "leave_policy.pdf",
  "document_id": 3,
  "page_number": 4,
  "section": "Leave Entitlement",
  "chunk_index": 12
}
```

**Query** — `question → (rewrite follow-up) → embed → search → rerank → prompt → LLM → answer + sources`.

Retrieval over-fetches `TOP_K × 3` candidates and re-ranks them with a blend of
vector similarity (65%), stemmed keyword overlap (25%) and section-title match
(10%), then drops anything below `MIN_RELEVANCE_SCORE`. That relevance floor is
what makes "I don't know" possible: with no chunk above the floor, there is nothing to answer from.

Full detail, including the layer boundaries and design trade-offs, is in
[`docs/architecture.md`](docs/architecture.md).

---

## Configuration

All settings come from environment variables (`.env`). See `.env.example` for the
full list; the ones you are most likely to touch:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | *(empty)* | Enables LLM answer generation. Empty = offline extractive mode. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible endpoint (Azure, vLLM, Ollama, OpenRouter…). |
| `LLM_MODEL` | `gpt-4o-mini` | Chat model. |
| `EMBEDDING_PROVIDER` | `auto` | `auto` / `openai` / `sentence_transformers` / `local`. |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model. |
| `TOP_K` | `4` | Chunks retrieved per question. |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `900` / `150` | Chunking window. |
| `MIN_RELEVANCE_SCORE` | `0.15` | Relevance floor for the "I don't know" path. |
| `DATABASE_URL` | `sqlite:///./hr_assistant.db` | Swap for a Postgres DSN to move to Postgres. |
| `JWT_SECRET_KEY` | `change_this_secret` | **Change this.** |
| `MAX_UPLOAD_MB` | `20` | Upload size limit. |

**Never commit `.env`.** It is in `.gitignore`.

### Choosing an embedding backend

`EMBEDDING_PROVIDER=auto` picks the best backend available:

1. **OpenAI** if `OPENAI_API_KEY` is set — best retrieval quality.
2. **sentence-transformers** if installed (`pip install sentence-transformers`) —
   good quality, fully local, needs a model download.
3. **local** hashed lexical embeddings — no downloads, no network, works
   everywhere. Lexical rather than semantic, so it matches wording more than
   meaning.

Changing the embedding backend changes the vector space, so **re-index after
switching**: delete `chroma_db/` and re-run `python -m backend.database.init_db`,
or press **Re-index** on each document in the dashboard.

---

## Running without an API key

The app is fully runnable with no LLM key, which makes it demo-safe on any
machine. With `OPENAI_API_KEY` empty it runs in **extractive mode**:

- retrieval, ChromaDB, citations, roles, history, feedback and analytics all work
  exactly the same;
- the answer is assembled from sentences quoted **verbatim** from the retrieved
  chunks, so it is grounded by construction and cannot hallucinate;
- a sentence must cover at least 60% of the question's meaningful words to be
  quoted — otherwise the assistant refuses.

The trade-off is fluency, not accuracy: extractive answers read like stitched
policy sentences rather than prose, and a question whose answer is spread across
a bulleted list may be refused even though the information is technically
present. Set `OPENAI_API_KEY` for synthesised answers; nothing else changes.

`/health` and the sidebar always report which mode is active.

---

## API reference

Interactive docs: http://localhost:8000/docs. Full reference with examples:
[`docs/api.md`](docs/api.md).

### Authentication
| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | public | Create an account |
| POST | `/api/auth/login` | public | Get an access token |
| GET | `/api/auth/me` | authenticated | Current user profile |

### Chat
| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/api/chat` | authenticated | Ask a question |
| GET | `/api/chat/history` | authenticated | List own conversations |
| GET | `/api/chat/{id}` | owner / admin | Conversation with messages |
| DELETE | `/api/chat/{id}` | owner | Delete a conversation |

### Documents (admin only)
| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/documents/upload` | Upload + index |
| GET | `/api/documents` | List documents |
| GET | `/api/documents/{id}` | Document metadata |
| DELETE | `/api/documents/{id}` | Delete document, file and vectors |
| POST | `/api/documents/{id}/reindex` | Re-run the ingestion pipeline |

### Feedback and analytics
| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| POST | `/api/feedback` | authenticated | Rate an answer |
| GET | `/api/feedback` | own / all for admin | List feedback |
| GET | `/api/admin/analytics` | admin | Usage metrics |
| GET | `/api/admin/questions` | admin | Recent questions |
| GET | `/api/admin/unanswered` | admin | Content gaps |

**Example**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"employee@acme.com","password":"Employee@123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"How many casual leaves do I get?","conversation_id":null}'
```

```json
{
  "answer": "Employees are eligible for 12 casual leaves per year.",
  "sources": [
    {"document": "leave_policy.pdf", "page": 4, "section": "Leave Entitlement", "score": 0.61}
  ],
  "conversation_id": 1,
  "message_id": 2,
  "answered": true,
  "latency_ms": 21
}
```

---

## Project layout

```
ai-hr-assistant/
├── backend/
│   ├── main.py                 FastAPI app, middleware, error handlers
│   ├── api/                    Thin HTTP routes (auth, chat, documents, feedback, admin)
│   ├── core/                   Config, logging, security, dependencies
│   ├── models/                 SQLAlchemy ORM models
│   ├── schemas/                Pydantic request/response schemas
│   ├── services/               Business logic (auth, chat, document, rag, llm, embedding)
│   ├── rag/                    RAG internals (loader, chunker, embeddings,
│   │                           vector_store, retriever, prompts, text_utils)
│   └── database/               Engine, session, init + seeding
├── frontend/
│   ├── app.py                  Streamlit entry point and role-based navigation
│   ├── api_client.py           REST client (the UI never touches the DB or LLM)
│   ├── state.py                Session-state helpers
│   ├── pages/                  login, employee_chat, chat_history, admin_dashboard
│   └── components/             chat, sources, sidebar
├── data/sample_hr_documents/   10 fictional HR policy PDFs
├── scripts/                    Sample-document generator, fine-tuning demo
├── tests/                      Auth, chat, documents, RAG, evaluation, frontend
├── docs/                       Architecture and API documentation
├── chroma_db/                  Vector store (generated)
├── uploads/                    Uploaded documents (generated)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

**Layering rule:** routes stay thin, business logic lives in `services/`, and RAG
internals live in `rag/`. A route never embeds text or builds a prompt.

---

## Testing and evaluation

```bash
pytest                        # everything (78 tests)
pytest tests/test_rag.py      # RAG pipeline only
pytest tests/test_evaluation.py -s   # scored evaluation report
```

Coverage: authentication and role enforcement, chat and follow-ups, conversation
ownership, document upload/validation/re-index/delete, chunking, retrieval,
grounding, citation correctness, and Streamlit page rendering.

The frontend tests need a running backend; they skip automatically without one.

### Evaluation harness

`tests/evaluation_questions.json` holds 16 labelled questions — 13 answerable,
3 deliberately not. `tests/test_evaluation.py` scores five dimensions and fails
the build if the pipeline regresses:

```
==============================================================
RAG EVALUATION REPORT
==============================================================
Retrieval relevance      : 100.0%  (13/13)
Answer correctness       : 100.0%  (13/13)
Groundedness             : 100.0%  (13/13)
Missing-answer handling  : 100.0%  (3/3)
Mean latency             :     14 ms
P95 latency              :     16 ms
==============================================================
```

(Offline extractive mode, local embeddings. Latency excludes LLM API time.)

- **Retrieval relevance** — did the expected document appear in the top-K?
- **Answer correctness** — does the answer contain the expected facts?
- **Groundedness** — is every cited source actually one of the retrieved chunks?
- **Missing-answer handling** — are unanswerable questions refused?
- **Latency** — mean and P95 end-to-end.

Add rows to the JSON file to grow the suite; no code changes needed.

---

## RAG vs fine-tuning

**Company knowledge belongs in RAG. Behaviour belongs in fine-tuning.**

| | RAG | Fine-tuning |
| --- | --- | --- |
| Holds | Policy facts, numbers, entitlements | Tone, structure, refusal style |
| Updates | Upload a document — instant | Retrain the model |
| Attribution | Cites document + page | None |
| Wrong-answer fix | Edit the document | Collect data, retrain |
| Cost | Per query | Per training run |

HR policy changes constantly, must be auditable, and must be citable — which is
exactly what RAG gives and fine-tuning does not. Baking "12 casual leaves" into
model weights means retraining every time HR edits the number, and the model will
still state the stale figure with total confidence and no source.

`scripts/finetune_demo.py` demonstrates the *correct* use of fine-tuning: a small
JSONL dataset that teaches response **style** (short, procedural, portal-first)
and consistent refusal — containing **zero** policy figures.

```bash
python -m scripts.finetune_demo --upload
```

It is optional and not needed for the demo.

---

## Security notes

Implemented:

- passwords hashed with PBKDF2-SHA256 (bcrypt hashes also verify)
- JWT bearer authentication with expiry
- role-based authorisation; all document and analytics routes are admin-only
- conversation ownership checks — an employee cannot read another's chat, and a
  probe for someone else's conversation id returns `404`, not `403`
- upload validation: extension allow-list, size limit, empty-file rejection, and
  filename sanitising (path components stripped)
- request validation on every endpoint via Pydantic
- API keys read from the environment, server-side only — the Streamlit frontend
  talks exclusively to the REST API and never sees a key
- logging that records login attempts, uploads, indexing and queries but never
  passwords, tokens, API keys or question text tied to identity
- generic 500 responses so internals are never leaked to clients

Before any real deployment: set a strong `JWT_SECRET_KEY`, change the seeded
accounts, put the API behind HTTPS, restrict CORS to your real frontend origin,
and move from SQLite to Postgres.

---

## Troubleshooting

**"Cannot reach the backend"** — start it: `uvicorn backend.main:app --reload`.
Check http://localhost:8000/health.

**Answers say the information could not be found** — check
`indexed_chunks` on `/health`. If it is `0`, run
`python -m backend.database.init_db`. If the documents are indexed, the question
may genuinely not be covered; look at **Content gaps** in the dashboard.

**Retrieval got worse after changing `EMBEDDING_PROVIDER`** — old vectors are in
the previous embedding space. Delete `chroma_db/` and re-index.

**ChromaDB fails to install or import** — the app automatically falls back to a
built-in JSON vector store with the same interface. `/health` reports which one
is active; everything else behaves identically.

**Upload rejected** — only `.pdf`, `.docx`, `.txt` and `.md` are accepted, up to
`MAX_UPLOAD_MB`. Scanned PDFs with no text layer will fail extraction (there is
no OCR).

**Port already in use** — `uvicorn ... --port 8010`, or
`streamlit run frontend/app.py --server.port 8502` (set `API_BASE_URL` to match).

---

## Notes on the sample data

Every document in `data/sample_hr_documents/` is fictional, generated by
`scripts/generate_sample_documents.py` for "ACME Corporation". No real company
policy and no real employee data appears anywhere in this project.
