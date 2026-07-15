"""
Central configuration. Reads everything from .env so no secrets are
hardcoded anywhere in the codebase. Copy .env.example to .env and fill
in GROQ_API_KEY before running anything.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    # Faster model for the sufficiency judge step
    GROQ_JUDGE_MODEL: str = os.getenv("GROQ_JUDGE_MODEL", "llama-3.1-8b-instant")

    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "../data/chroma_db")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "../data/uploads")

    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # 1 attempt keeps latency low; the 8b judge model is fast enough
    # that a single pass is usually sufficient for well-formed questions.
    MAX_RETRIEVAL_ATTEMPTS: int = int(os.getenv("MAX_RETRIEVAL_ATTEMPTS", 1))
    TOP_K_CHUNKS: int = int(os.getenv("TOP_K_CHUNKS", 3))

    # Reranking: vector search pulls a wider candidate pool, a cross encoder
    # rescores each one against the exact question, then only the best
    # TOP_K_CHUNKS survive. Free, local model — no API cost.
    RERANK_ENABLED: bool = os.getenv("RERANK_ENABLED", "true").lower() == "true"
    RERANK_MODEL: str = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    RERANK_CANDIDATE_POOL: int = int(os.getenv("RERANK_CANDIDATE_POOL", 6))

    CHUNK_SIZE: int = 800       # characters per chunk
    CHUNK_OVERLAP: int = 150    # overlap to avoid losing context at boundaries

    COLLECTION_NAME: str = "documents"

    # Security: max upload file size in MB
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", 100))


settings = Settings()

if not settings.GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is missing. Copy backend/.env.example to backend/.env "
        "and add your free key from https://console.groq.com"
    )
