"""
The core "agentic" piece. Plain RAG does: query -> retrieve -> generate.
This does: query -> retrieve -> LLM JUDGES if the retrieved chunks are
actually enough to answer -> if not, LLM REWRITES the query and retries
(up to MAX_RETRIEVAL_ATTEMPTS) -> only then generates a final answer,
and the answer is required to cite [source, page] for every claim.

This self-correction loop is what separates "agentic RAG" from a
plain vector-search-and-stuff-into-prompt pipeline.

Formatting improvements:
- Structured output with clear sections, numbered lists, paragraphs
- No leading dashes or em-dashes (removes AI-generated look)
- Rich chunk context shown in response for user transparency
"""
from __future__ import annotations

import json
import time
import logging
from typing import List, Dict

from groq import Groq

from rag.config import settings
from rag.retriever import retrieve

logger = logging.getLogger(__name__)
client = Groq(api_key=settings.GROQ_API_KEY)


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
    model: str | None = None,
) -> str:
    """Call the Groq LLM. Accepts an optional model override so the
    judge step can use a smaller, faster model."""
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(
        model=model or settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=1024,
        **kwargs,
    )
    return response.choices[0].message.content


def _judge_sufficiency(question: str, chunks: List[Dict]) -> Dict:
    """
    Asks the LLM: is this retrieved context actually enough to answer
    the question fully and accurately? Returns a structured verdict.
    This is the "self-correction" checkpoint.

    Uses the faster GROQ_JUDGE_MODEL (8B) instead of the full model
    since a yes/no + reason verdict doesn't need maximum reasoning.
    """
    # Truncated to 200 chars per chunk — reduces input tokens
    # for faster judge inference without losing meaningful signal
    context_preview = "\n\n".join(
        f"[{c['source']} - page {c['page_number']}] {c['text'][:200]}"
        for c in chunks
    ) or "No context retrieved."

    system_prompt = (
        "You are a strict retrieval quality judge for a RAG system. "
        "Given a user question and retrieved context chunks, decide if the "
        "context is SUFFICIENT to fully and accurately answer the question. "
        "Respond ONLY in JSON with keys: "
        '{"sufficient": true|false, "reason": "short reason", '
        '"better_query": "a rewritten search query if not sufficient, else empty string"}'
    )
    user_prompt = f"Question: {question}\n\nRetrieved context:\n{context_preview}"

    raw = _call_llm(
        system_prompt,
        user_prompt,
        json_mode=True,
        model=settings.GROQ_JUDGE_MODEL,
    )
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        # Fail safe: if the judge itself breaks, treat context as sufficient
        # so the pipeline doesn't loop forever or crash.
        return {"sufficient": True, "reason": "judge_parse_failed", "better_query": ""}


def _generate_cited_answer(question: str, chunks: List[Dict]) -> str:
    """
    Generates the final answer with strict formatting rules:
    - Structured output: bold headers, numbered lists, clear paragraphs
    - No leading dashes or em-dashes (removes AI-generated text feel)
    - Citation of [source, page] after every factual claim
    - No hallucination outside the given context
    """
    context_block = "\n\n".join(
        f"[Source: {c['source']}, Page: {c['page_number']}]\n{c['text']}"
        for c in chunks
    )

    system_prompt = (
        "You are a precise document Q&A assistant. Answer the user's question "
        "using ONLY the provided context chunks.\n\n"
        "STRICT FORMATTING RULES — follow these exactly:\n"
        "1. Start with a short 1-2 sentence summary paragraph answering the question directly.\n"
        "2. If there are multiple points, use numbered lists: '1. ', '2. ', '3. ' etc.\n"
        "3. Group related points under **Bold Section Headers** when needed.\n"
        "4. Write in clear, direct sentences. Keep paragraphs to 2-3 sentences max.\n"
        "5. NEVER use a dash character (- or —) to start any line, sentence, or list item.\n"
        "6. NEVER use bullet points with dashes. Use numbered lists only.\n"
        "7. After every factual sentence or claim, add a citation: (Source: <name>, Page: <n>).\n"
        "8. If the context does not contain the answer, write exactly: "
        "'The provided documents do not contain enough information to answer this question.'\n"
        "9. Do not use outside knowledge. Do not make up page numbers.\n"
        "10. End with a concise summary sentence if the answer has multiple sections."
    )
    user_prompt = f"Context:\n{context_block}\n\nQuestion: {question}"

    return _call_llm(system_prompt, user_prompt)


def _clean_answer(text: str) -> str:
    """Post-process the answer to remove any remaining AI-generated artifacts
    like leading dashes that the model might still produce despite instructions."""
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.lstrip()
        # Replace leading dash+space with nothing (inline numbered format instead)
        if stripped.startswith('- ') or stripped.startswith('— '):
            indent = len(line) - len(stripped)
            line = ' ' * indent + stripped[2:]
        elif stripped.startswith('–'):
            indent = len(line) - len(stripped)
            line = ' ' * indent + stripped[1:].lstrip()
        cleaned.append(line)
    return '\n'.join(cleaned)


def answer_question(question: str) -> Dict:
    """
    Full agentic pipeline. Returns a dict with the final answer, the
    chunks actually used (including chunk text for UI display), how many
    retrieval attempts it took, and the query rewrite history.

    Includes timing instrumentation for performance profiling.
    """
    pipeline_start = time.time()
    attempt_log = []
    current_query = question
    chunks: List[Dict] = []

    for attempt in range(1, settings.MAX_RETRIEVAL_ATTEMPTS + 1):
        t0 = time.time()
        chunks = retrieve(current_query)
        retrieval_ms = round((time.time() - t0) * 1000)

        if not chunks:
            attempt_log.append({
                "attempt": attempt, "query": current_query,
                "verdict": "no_chunks_found",
            })
            logger.info(f"Attempt {attempt}: no chunks found ({retrieval_ms}ms)")
            break

        t0 = time.time()
        verdict = _judge_sufficiency(question, chunks)
        judge_ms = round((time.time() - t0) * 1000)

        attempt_log.append({
            "attempt": attempt,
            "query": current_query,
            "sufficient": verdict.get("sufficient"),
            "reason": verdict.get("reason"),
        })

        logger.info(
            f"Attempt {attempt}: retrieval={retrieval_ms}ms, "
            f"judge={judge_ms}ms, sufficient={verdict.get('sufficient')}"
        )

        if verdict.get("sufficient"):
            break

        next_query = verdict.get("better_query") or current_query
        if next_query == current_query:
            # Judge didn't propose anything new, no point looping further.
            break
        current_query = next_query

    if not chunks:
        return {
            "question": question,
            "answer": "No relevant documents found. Please ingest a document first.",
            "sources_used": [],
            "retrieval_attempts": attempt_log,
        }

    t0 = time.time()
    raw_answer = _generate_cited_answer(question, chunks)
    # Post-process to remove any remaining dashes the model may have added
    final_answer = _clean_answer(raw_answer)
    generate_ms = round((time.time() - t0) * 1000)
    total_ms = round((time.time() - pipeline_start) * 1000)

    logger.info(f"Answer generation: {generate_ms}ms | Total pipeline: {total_ms}ms")

    # Include chunk_text so the frontend can show which exact passage was used
    sources_used = [
        {
            "source": c["source"],
            "page_number": c["page_number"],
            "relevance_score": c["relevance_score"],
            "chunk_text": c["text"],
        }
        for c in chunks
    ]

    return {
        "question": question,
        "answer": final_answer,
        "sources_used": sources_used,
        "retrieval_attempts": attempt_log,
    }
