"""
FastAPI backend for the Agentic RAG system.
No UI here by design — Antigravity/your frontend calls these endpoints.
Run with: uvicorn main:app --reload --port 8000
Docs auto-generated at http://localhost:8000/docs
"""
import asyncio
import re
import unicodedata
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag.config import settings
from rag.ingest import ingest_pdf, list_ingested_sources
from rag.agent import answer_question

app = FastAPI(
    title="Agentic RAG API",
    description="Self-correcting, citation-enforced RAG over your PDF documents.",
    version="1.0.0",
)

# Wide open for local dev / Antigravity frontend. Tighten allow_origins
# before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


class QueryRequest(BaseModel):
    question: str


class SourceChunk(BaseModel):
    source: str
    page_number: int
    relevance_score: float
    chunk_text: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources_used: list
    retrieval_attempts: list


def _secure_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal attacks.
    Strips directory components, replaces dangerous characters,
    and ensures only safe characters remain."""
    # Normalize unicode to prevent sneaky bypasses
    filename = unicodedata.normalize("NFKD", filename)
    # Take only the basename — strips ../../ or C:\\ prefixes
    filename = filename.replace("\\", "/")
    filename = filename.split("/")[-1]
    # Remove any non-alphanumeric character except dot, dash, underscore, space
    filename = re.sub(r"[^\w\s\-.]", "", filename).strip()
    # Collapse whitespace
    filename = re.sub(r"\s+", "_", filename)
    # Prevent empty or hidden filenames
    if not filename or filename.startswith("."):
        filename = "upload.pdf"
    return filename


@app.on_event("startup")
async def warmup_models():
    """Pre-load the embedding model and reranker in background threads at
    startup so the first ingest/query request doesn't pay the cold-start
    penalty (model loading can take 5-10s on first run).
    Runs asynchronously — server is ready to accept requests immediately."""
    async def _warmup():
        try:
            # Import here to avoid circular imports at module level
            from rag.ingest import _get_embedder as get_ingest_embedder
            from rag.retriever import _get_embedder as get_retriever_embedder
            from rag.retriever import _get_reranker

            import logging
            logger = logging.getLogger("warmup")
            logger.info("Warming up embedding model...")
            await asyncio.to_thread(get_ingest_embedder)
            await asyncio.to_thread(get_retriever_embedder)
            logger.info("Warming up reranker model...")
            await asyncio.to_thread(_get_reranker)
            logger.info("Models warmed up. Ingestion will be fast.")
        except Exception as e:
            import logging
            logging.getLogger("warmup").warning(f"Warmup failed (non-fatal): {e}")

    asyncio.create_task(_warmup())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
async def ingest_document(file: UploadFile = File(...)):
    """Upload a PDF. It gets chunked, embedded, and stored locally."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")

    safe_name = _secure_filename(file.filename)
    save_path = Path(settings.UPLOAD_DIR) / safe_name

    # Stream the file to disk in chunks instead of reading all at once.
    # This prevents memory spikes on large PDFs (200+ pages).
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    total_written = 0
    chunk_size = 64 * 1024  # 64KB chunks

    try:
        with open(save_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_written += len(chunk)
                if total_written > max_bytes:
                    # Clean up the partial file
                    f.close()
                    save_path.unlink(missing_ok=True)
                    raise HTTPException(
                        413,
                        f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB."
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Failed to save file: {str(e)}")

    # Run ingestion in a thread pool so the CPU-heavy embedding work
    # doesn't block the async event loop (which would freeze health
    # checks and other requests during long ingestion).
    try:
        result = await asyncio.to_thread(
            ingest_pdf, str(save_path), source_name=safe_name
        )
    except ValueError as e:
        raise HTTPException(422, str(e))

    return result


@app.get("/documents")
def get_documents():
    """List all documents currently searchable."""
    return {"sources": list_ingested_sources()}


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Ask a question. Runs the full agentic retrieve -> judge -> retry
    -> cited-answer pipeline and returns the answer with sources."""
    if not request.question.strip():
        raise HTTPException(400, "Question cannot be empty.")

    # Run in thread pool — the pipeline makes blocking HTTP calls to Groq
    result = await asyncio.to_thread(answer_question, request.question)
    return result
