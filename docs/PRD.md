# PRD — Agentic RAG Document Q&A (Frontend)

## 1. Product summary
A web app where a user uploads PDF document(s) and asks questions about
them in a chat interface. The backend already exists and is agentic:
it self-corrects retrieval before answering, and every answer includes
inline citations (source file + page number). The frontend's job is to
present this clearly and make the "why should I trust this answer"
story visible.

## 2. Target user
Freelance client demo / portfolio viewer: recruiters, potential
freelance clients (legal, HR, research teams) evaluating whether this
tool could replace manual document search.

## 3. Core user flow
1. User lands on the app, sees an upload area and empty chat.
2. User uploads one or more PDFs -> sees ingestion status (pages,
   chunks created) per file.
3. User types a question in a chat box.
4. While processing, UI shows a subtle "thinking" state — ideally
   reflecting that retrieval may retry (e.g. "Searching...",
   "Refining search...", "Generating answer...").
5. Answer appears with inline citations rendered as small clickable
   badges, e.g. `[contract.pdf, p.4]`.
6. Below/beside the answer, show a collapsible "Sources used" panel
   listing each retrieved chunk's source, page, and relevance score.
7. Optionally show "Retrieval attempts" as a small expandable trace
   (this is a differentiator — most demos hide this, showing it
   proves the system is agentic, not just a wrapper).

## 4. Screens / components needed
- **Upload panel**: drag-drop or file picker, list of ingested
  documents with chunk counts, delete/re-upload not required for v1.
- **Chat panel**: standard chat bubble UI, user question right-aligned,
  assistant answer left-aligned with citation badges inline.
- **Sources drawer**: expandable panel per answer showing
  source/page/relevance_score for each chunk used.
- **Attempt trace (optional, nice-to-have)**: small expandable log
  showing query rewrites if the agent had to retry retrieval.
- **Empty/error states**: "No documents ingested yet", "This PDF has
  no extractable text (likely scanned)", "No relevant info found".

## 5. Non-functional requirements
- No UI is built in this repo — it comes from Antigravity separately.
- Frontend must call backend at `http://localhost:8000` in dev (see
  API_SPEC.md for exact endpoints/schemas).
- Response times: ingestion can take 5-30s per PDF depending on size
  (local embedding model), queries take 3-10s (agentic loop may call
  the LLM up to 4 times). UI must show loading states, not appear frozen.
- Must work with zero paid services — backend already guarantees this;
  frontend should not introduce paid APIs either.

## 6. Explicit non-goals (v1)
- No user authentication.
- No multi-user/tenant separation.
- No streaming token-by-token responses (can be a v2 enhancement).
- No editing/deleting ingested documents via UI.

## 7. Success criteria
- A user can upload a real PDF and get a correctly cited answer within
  ~15 seconds.
- The demo visibly communicates "this isn't a plain chatbot" via the
  sources panel and (optionally) the retry trace.
