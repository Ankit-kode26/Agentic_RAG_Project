# API Spec — for Antigravity frontend integration

Base URL (local dev): `http://localhost:8000`
Interactive docs (auto-generated, try it live): `http://localhost:8000/docs`

---

### `GET /health`
Check if backend is running.

**Response**
```json
{ "status": "ok" }
```

---

### `POST /ingest`
Upload one PDF for indexing. `multipart/form-data`, field name `file`.

**Response**
```json
{
  "source": "contract.pdf",
  "pages_ingested": 12,
  "chunks_created": 34
}
```

**Errors**
- `400` — file is not a PDF
- `422` — PDF has no extractable text (likely scanned/image-only)

---

### `GET /documents`
List all documents currently indexed and searchable.

**Response**
```json
{ "sources": ["contract.pdf", "handbook.pdf"] }
```

---

### `POST /query`
Ask a question over all currently ingested documents.

**Request**
```json
{ "question": "What is the notice period for termination?" }
```

**Response**
```json
{
  "question": "What is the notice period for termination?",
  "answer": "The notice period is 30 days (Source: contract.pdf, Page: 4).",
  "sources_used": [
    { "source": "contract.pdf", "page_number": 4, "relevance_score": 0.87 },
    { "source": "contract.pdf", "page_number": 5, "relevance_score": 0.71 }
  ],
  "retrieval_attempts": [
    { "attempt": 1, "query": "notice period for termination", "sufficient": true, "reason": "context directly answers the question" }
  ]
}
```

Notes for frontend:
- `answer` contains inline text like `(Source: file.pdf, Page: 4)` —
  parse this to render clickable citation badges if desired.
- `retrieval_attempts` can have more than one entry if the agent had
  to rewrite its search query — useful for an optional "trace" UI.
- Expect 3-10 second response times; show a loading state.

**Errors**
- `400` — empty question string

---

### CORS
Backend allows all origins in dev (`allow_origins=["*"]`). No auth
headers needed for local development.
