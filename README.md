# Agentic RAG — Setup

## 1. Get your free API key
Sign up at https://console.groq.com (no credit card required) and
copy your API key.

## 2. Setup
```bash
cd backend
cp .env.example .env
# open .env and paste your GROQ_API_KEY

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Run
```bash
uvicorn main:app --reload --port 8000
```
Open http://localhost:8000/docs to test ingestion and queries directly
(no frontend needed to verify it works).

## 4. Try it
1. In `/docs`, use `POST /ingest` to upload a PDF.
2. Use `POST /query` with a question about that PDF.
3. Check the `answer` field — it should cite `(Source: ..., Page: ...)`.

## 5. Run the evaluation (for your portfolio README/case study)
```bash
python evaluate.py test_questions.sample.json
```
This prints a groundedness score and writes `eval_report.json` — put
the score in your project's README, e.g. "Groundedness: 92% (23/25)".

## 6. Cost
$0. Groq free tier + local embeddings (sentence-transformers) + local
ChromaDB. No credit card required anywhere in this stack.

## Docs for frontend build (Antigravity)
See `/docs/PRD.md`, `/docs/ARCHITECTURE.md`, `/docs/API_SPEC.md`.
