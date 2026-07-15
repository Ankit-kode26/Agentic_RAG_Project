"""
Evaluation script — run this after ingesting documents and asking
questions through the API a few times, or feed it a test set directly.

It checks: for each answer, does every citation in the answer actually
point to a source/page that was in sources_used? This is a simple but
real "groundedness" check — it catches the LLM citing a page that
wasn't actually retrieved (a common hallucination pattern).

Usage:
    python evaluate.py test_questions.json

test_questions.json format:
    [{"question": "What is the notice period for termination?"}, ...]

Produces eval_report.json with pass/fail per question and an overall
groundedness score you can put directly in your portfolio README:
"Groundedness: 92% (23/25 answers fully cited from retrieved context)"
"""
import json
import re
import sys
from pathlib import Path

from rag.agent import answer_question


def _extract_cited_pages(answer_text: str) -> set:
    """Pulls out (Source: X, Page: N) citations from the generated answer."""
    pattern = r"Source:\s*([^,]+),\s*Page:\s*(\d+)"
    return {(m[0].strip(), int(m[1])) for m in re.findall(pattern, answer_text)}


def evaluate(questions_path: str):
    questions = json.loads(Path(questions_path).read_text())
    report = []

    for item in questions:
        q = item["question"]
        result = answer_question(q)

        retrieved_pages = {
            (s["source"], s["page_number"]) for s in result["sources_used"]
        }
        cited_pages = _extract_cited_pages(result["answer"])

        # A citation is "ungrounded" if the answer cites a page that
        # wasn't actually in the retrieved context (i.e. made up).
        ungrounded = cited_pages - retrieved_pages
        has_any_citation = len(cited_pages) > 0
        fully_grounded = has_any_citation and len(ungrounded) == 0

        report.append({
            "question": q,
            "answer_snippet": result["answer"][:200],
            "citations_found": len(cited_pages),
            "ungrounded_citations": list(ungrounded),
            "fully_grounded": fully_grounded,
            "retrieval_attempts_needed": len(result["retrieval_attempts"]),
        })

    total = len(report)
    grounded_count = sum(1 for r in report if r["fully_grounded"])
    groundedness_pct = round(100 * grounded_count / total, 1) if total else 0.0

    summary = {
        "total_questions": total,
        "fully_grounded_answers": grounded_count,
        "groundedness_score_pct": groundedness_pct,
        "details": report,
    }

    Path("eval_report.json").write_text(json.dumps(summary, indent=2))
    print(f"Groundedness score: {groundedness_pct}% ({grounded_count}/{total})")
    print("Full report saved to eval_report.json")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python evaluate.py test_questions.json")
        sys.exit(1)
    evaluate(sys.argv[1])
