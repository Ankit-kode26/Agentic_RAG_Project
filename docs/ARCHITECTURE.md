# Architecture — Agentic RAG Backend

## System diagram (textual)

```
PDF upload
   |
   v
[ingest.py] --extract pages (pypdf)--> [chunk with overlap] --> [embed: sentence-transformers, local]
   |
   v
[ChromaDB - local persistent vector store]  (metadata: source filename, page number)

User question
   |
   v
[agent.py] --retrieve(query)--> [retriever.py]
   |
   v
Stage 1: ChromaDB vector search --> wide candidate pool (20 chunks)
   |
   v
Stage 2: cross-encoder reranks candidates against exact question --> top 5 kept
   |
   v
[LLM judges: is this context sufficient?]  (Groq API)
   |
   |-- no --> rewrite query --> retry retrieval (up to MAX_RETRIEVAL_ATTEMPTS)
   |
   yes
   v
[LLM generates answer, forced to cite (source, page) per claim]  (Groq API)
   |
   v
JSON response: { answer, sources_used[], retrieval_attempts[] }
```

## Why each design choice

- **Local embeddings (sentence-transformers) instead of an embedding
  API**: keeps cost at $0 and avoids rate limits during repeated
  ingestion/testing. Trade-off: slightly lower embedding quality than
  OpenAI's, acceptable for a portfolio/demo scale.
- **ChromaDB persistent local store instead of Pinecone/managed
  vector DB**: also $0, no account needed, good enough for
  single-user/demo scale. Documented limitation: doesn't scale to
  many concurrent users — worth mentioning honestly in any client
  conversation as the exact kind of production constraint a real team
  would face.
- **Groq for the LLM**: free tier, fast inference, supports JSON mode
  which the "judge" step depends on for structured verdicts.
- **Page-level metadata on every chunk**: this is what makes citation
  possible at all — decided at ingestion time, can't be bolted on
  later without re-ingesting.
- **Two-stage retrieval (vector search then cross-encoder rerank)**:
  vector similarity alone often ranks a "kind of related" chunk above
  the actually-correct one because it only compares embeddings, not
  the real question against the real text. A cross-encoder reads the
  question and chunk together and scores true relevance, which
  measurably improves which chunks reach the LLM. Cost stays $0 since
  `cross-encoder/ms-marco-MiniLM-L-6-v2` runs locally on CPU. Trade-off:
  adds roughly 0.5-2s latency per query since the pool must be scored
  one-by-one instead of just an ANN lookup — acceptable given the
  accuracy gain.
- **Judge-then-retry loop capped at MAX_RETRIEVAL_ATTEMPTS**: prevents
  infinite loops if the LLM judge keeps saying "insufficient" — always
  terminates and returns the best answer it has.
- **Citation enforcement via prompt + evaluation script**: the prompt
  asks the LLM to cite, but prompts aren't guaranteed — `evaluate.py`
  independently checks whether cited pages were actually retrieved,
  catching cases where the LLM cites something it made up.

## File structure

```
agentic-rag/
├── backend/
│   ├── main.py                  # FastAPI app, all HTTP endpoints
│   ├── evaluate.py               # groundedness evaluation script
│   ├── requirements.txt
│   ├── .env.example
│   ├── test_questions.sample.json
│   └── rag/
│       ├── config.py             # settings from .env
│       ├── ingest.py             # PDF -> chunks -> embeddings -> ChromaDB
│       ├── retriever.py          # similarity search over ChromaDB
│       └── agent.py              # agentic judge-retry-generate loop
├── data/
│   ├── uploads/                  # uploaded PDFs land here
│   └── chroma_db/                # persistent vector store (auto-created)
└── docs/
    ├── PRD.md
    ├── ARCHITECTURE.md
    └── API_SPEC.md
```

## Known limitations (be upfront about these — it builds credibility)

- Scanned/image-only PDFs won't extract text (no OCR in v1).
- Single global collection — all uploaded documents are searched
  together; no per-session isolation.
- No conversation memory — each question is independent (no
  multi-turn follow-up context yet).
- No streaming responses — the full answer arrives at once.
