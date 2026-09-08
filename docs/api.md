# API reference

Base URL: `http://localhost:8000`
Interactive docs: `/docs` (Swagger) · `/redoc`

All endpoints except `/`, `/health`, `/api/auth/register` and `/api/auth/login`
require a bearer token:

```
Authorization: Bearer <access_token>
```

---

## Conventions

### Error format

Every error returns the same shape:

```json
{ "detail": "Human-readable description" }
```

### Status codes

| Code | Meaning |
| --- | --- |
| `200` | Success |
| `201` | Created (register, upload, feedback) |
| `204` | Deleted, no content |
| `400` | Invalid file type, empty file, file too large |
| `401` | Missing, malformed or expired token; bad credentials |
| `403` | Authenticated but wrong role (admin-only route) |
| `404` | Not found, or not owned by the caller |
| `409` | Email already registered |
| `422` | Request body failed validation |
| `500` | Unexpected server error (details are logged, not returned) |
| `503` | Embedding service or vector database unavailable |

---

## Health

### `GET /`

```json
{ "service": "AI HR Assistant", "version": "1.0.0", "docs": "/docs" }
```

### `GET /health`

Reports which backends are active — useful for confirming the deployment mode.

```json
{
  "status": "ok",
  "embedding_provider": "local-hash",
  "vector_store": "chromadb",
  "indexed_chunks": 57,
  "llm_mode": "extractive",
  "llm_model": null,
  "top_k": 4
}
```

`llm_mode` is `"llm"` when `OPENAI_API_KEY` is set, otherwise `"extractive"`.

---

## Authentication

### `POST /api/auth/register`

Creates an account and returns a token. Role defaults to `employee`.

**Request**
```json
{
  "name": "Priya Sharma",
  "email": "priya@acme.com",
  "password": "Str0ngPass!",
  "role": "employee"
}
```

| Field | Rules |
| --- | --- |
| `name` | 2–120 characters |
| `email` | valid email, unique |
| `password` | 8–128 characters |
| `role` | `employee` (default) or `admin` |

**Response `201`**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 3,
    "name": "Priya Sharma",
    "email": "priya@acme.com",
    "role": "employee",
    "created_at": "2025-01-15T09:30:00"
  }
}
```

**Errors** — `409` email already registered · `422` validation failed

> In a real deployment, self-registration with `role: "admin"` should be removed
> or gated. It is left open here so the demo can create either role.

---

### `POST /api/auth/login`

**Request**
```json
{ "email": "employee@acme.com", "password": "Employee@123" }
```

**Response `200`** — same shape as register.

**Errors** — `401` invalid email or password (identical response either way, so
the endpoint cannot be used to enumerate accounts).

---

### `GET /api/auth/me`

**Response `200`**
```json
{
  "id": 2,
  "name": "Demo Employee",
  "email": "employee@acme.com",
  "role": "employee",
  "created_at": "2025-01-15T09:30:00"
}
```

---

## Chat

### `POST /api/chat`

Ask a question. Pass `conversation_id: null` to start a new conversation, or an
existing id to continue one (which enables follow-up context).

**Request**
```json
{ "question": "How many casual leaves do I get?", "conversation_id": null }
```

**Response `200`**
```json
{
  "answer": "Employees are eligible for 12 casual leaves per year.",
  "sources": [
    {
      "document": "leave_policy.pdf",
      "page": 4,
      "section": "Leave Entitlement",
      "score": 0.6142
    }
  ],
  "conversation_id": 1,
  "message_id": 2,
  "answered": true,
  "latency_ms": 21
}
```

| Field | Meaning |
| --- | --- |
| `answer` | The generated or extracted answer |
| `sources` | Citations, deduplicated by document + page. **Empty when `answered` is false.** |
| `conversation_id` | Use this on the next request to continue the thread |
| `message_id` | The assistant message — pass to `/api/feedback` |
| `answered` | `false` when the documents did not cover the question |
| `latency_ms` | End-to-end time for retrieval + generation |

**When the answer is not in the documents**
```json
{
  "answer": "I could not find this information in the available HR documents. Please contact the HR department for clarification.",
  "sources": [],
  "conversation_id": 4,
  "message_id": 9,
  "answered": false,
  "latency_ms": 12
}
```

**Errors** — `401` no token · `404` unknown conversation, or not yours ·
`422` empty question · `503` embeddings or vector DB unavailable

---

### `GET /api/chat/history`

The caller's conversations, most recently updated first.

**Response `200`**
```json
[
  {
    "id": 2,
    "title": "What is the work from home policy?",
    "message_count": 4,
    "created_at": "2025-01-15T10:02:00",
    "updated_at": "2025-01-15T10:06:30"
  }
]
```

Titles are derived from the first question, truncated to 60 characters.

---

### `GET /api/chat/{conversation_id}`

Full conversation with messages. Employees may read only their own; admins may
read any.

**Response `200`**
```json
{
  "id": 1,
  "title": "How many casual leaves do I get?",
  "message_count": 2,
  "created_at": "2025-01-15T10:00:00",
  "updated_at": "2025-01-15T10:00:01",
  "messages": [
    {
      "id": 1,
      "role": "user",
      "content": "How many casual leaves do I get?",
      "sources": [],
      "answered": true,
      "created_at": "2025-01-15T10:00:00"
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "Employees are eligible for 12 casual leaves per year.",
      "sources": [{ "document": "leave_policy.pdf", "page": 4, "section": "Leave Entitlement", "score": 0.61 }],
      "answered": true,
      "created_at": "2025-01-15T10:00:01"
    }
  ]
}
```

**Errors** — `404` unknown id, **or the conversation belongs to another user**
(deliberately indistinguishable, so ids cannot be probed).

---

### `DELETE /api/chat/{conversation_id}`

Deletes the conversation and its messages. **Response `204`**, no body.

---

## Documents — admin only

Every route below returns `403` for a non-admin token.

### `POST /api/documents/upload`

`multipart/form-data` with a single `file` field. Upload and indexing are
synchronous: the response reflects the real indexing outcome.

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@leave_policy.pdf"
```

**Response `201`**
```json
{
  "document": {
    "id": 3,
    "filename": "leave_policy.pdf",
    "file_type": ".pdf",
    "file_size": 48213,
    "status": "indexed",
    "chunk_count": 8,
    "uploaded_by": 1,
    "error_message": null,
    "created_at": "2025-01-15T09:40:00",
    "updated_at": "2025-01-15T09:40:02"
  },
  "message": "Document indexed successfully (8 chunks)"
}
```

**Constraints** — `.pdf`, `.docx`, `.txt`, `.md` · max `MAX_UPLOAD_MB` (20 by
default) · non-empty.

If extraction fails the response is still `201` but with
`status: "failed"`, a populated `error_message`, and a `message` explaining the
failure — the file is stored so the admin can inspect or re-index it.

**Errors** — `400` bad type / empty / too large · `403` not an admin

---

### `GET /api/documents`

**Response `200`** — array of document objects, newest first.

### `GET /api/documents/{document_id}`

**Response `200`** — one document object. `404` if unknown.

### `DELETE /api/documents/{document_id}`

Removes the database row, the file on disk **and** the document's vectors from
ChromaDB, so it stops appearing in answers immediately. **Response `204`**.

### `POST /api/documents/{document_id}/reindex`

Re-runs extraction → chunking → embedding → storage. Old vectors are deleted
first, so re-indexing never duplicates chunks. Use after changing
`CHUNK_SIZE`, `CHUNK_OVERLAP` or `EMBEDDING_PROVIDER`.

**Response `200`** — the updated document object.
**Errors** — `404` unknown id · `422` re-indexing failed (message included)

### `GET /api/documents/config/limits`

```json
{ "allowed_extensions": [".pdf", ".docx", ".txt", ".md"], "max_upload_mb": 20 }
```

---

## Feedback

### `POST /api/feedback`

Rate an assistant answer. Re-rating the same message **updates** the existing
row rather than creating a duplicate.

**Request**
```json
{
  "conversation_id": 1,
  "message_id": 2,
  "rating": "positive",
  "comment": "Helpful answer"
}
```

| Field | Rules |
| --- | --- |
| `rating` | `positive` or `negative` |
| `comment` | optional, ≤ 1000 characters |

**Response `201`**
```json
{
  "id": 1,
  "conversation_id": 1,
  "message_id": 2,
  "rating": "positive",
  "comment": "Helpful answer",
  "created_at": "2025-01-15T10:05:00"
}
```

**Errors** — `404` conversation or message not found (or not yours) ·
`422` invalid rating

### `GET /api/feedback`

Admins get all feedback; employees get only their own. **Response `200`** — array
of feedback objects, newest first.

---

## Admin analytics — admin only

### `GET /api/admin/analytics`

```json
{
  "total_questions": 125,
  "total_documents": 10,
  "indexed_documents": 10,
  "total_users": 12,
  "positive_feedback": 108,
  "negative_feedback": 17,
  "unanswered_questions": 5,
  "satisfaction_rate": 86.4,
  "avg_latency_ms": 940,
  "indexed_chunks": 57
}
```

`satisfaction_rate` is positive ÷ total rated, as a percentage; `0.0` when
nothing has been rated yet.

### `GET /api/admin/questions?limit=50`

Recent employee questions with the answered flag of the reply.

```json
{
  "items": [
    {
      "message_id": 41,
      "conversation_id": 17,
      "user_email": "employee@acme.com",
      "question": "How many casual leaves do I get?",
      "answered": true,
      "created_at": "2025-01-15T10:00:00"
    }
  ],
  "total": 125
}
```

`limit` — 1 to 500, default 50.

### `GET /api/admin/unanswered?limit=50`

Same shape, filtered to questions the documents did not cover. This is the
content-gap backlog: each row is a policy the HR team may need to write or
upload.

---

## Complete worked example

```bash
BASE=http://localhost:8000

# 1. Employee logs in
TOKEN=$(curl -s -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"employee@acme.com","password":"Employee@123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. Ask a question
RESPONSE=$(curl -s -X POST $BASE/api/chat \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"How many casual leaves do I get?","conversation_id":null}')
echo "$RESPONSE"

CONV=$(echo "$RESPONSE" | python -c "import sys,json;print(json.load(sys.stdin)['conversation_id'])")
MSG=$(echo "$RESPONSE"  | python -c "import sys,json;print(json.load(sys.stdin)['message_id'])")

# 3. Follow-up in the same conversation
curl -s -X POST $BASE/api/chat \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"question\":\"Can I carry them forward?\",\"conversation_id\":$CONV}"

# 4. Rate the first answer
curl -s -X POST $BASE/api/feedback \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"conversation_id\":$CONV,\"message_id\":$MSG,\"rating\":\"positive\"}"

# 5. Admin uploads a document and checks analytics
ADMIN=$(curl -s -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@acme.com","password":"Admin@123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -X POST $BASE/api/documents/upload \
  -H "Authorization: Bearer $ADMIN" -F "file=@new_policy.pdf"

curl -s $BASE/api/admin/analytics -H "Authorization: Bearer $ADMIN"
curl -s $BASE/api/admin/unanswered -H "Authorization: Bearer $ADMIN"
```
