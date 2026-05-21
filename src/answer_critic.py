"""V3 answer critic for self-checking finance RAG responses."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config import CHAT_MODEL


CRITIC_PROMPT = """You are an answer quality critic for a finance RAG system.

Your job is to review the draft answer against the retrieved evidence.
Do not introduce new facts.
Do not invent new sources.
If the answer overclaims, rewrite it more carefully.
If evidence is missing, say so clearly.
If the answer does not directly answer the user's question, improve it.

Check these criteria:
- Directness: does the answer directly answer the user question?
- Evidence grounding: does it only use retrieved evidence?
- Risk comparison quality: does it compare requested risks across the requested banks?
- Uncertainty handling: does it distinguish actual risk, retrieved evidence strength, and disclosure detail?
- Consultant recommendation quality: does it mention further due diligence and quantitative indicators?
- Source discipline: does it preserve sources and avoid inventing new ones?

Keep the same consulting-style structure:
- Executive Summary
- Key Evidence
- Risk Flags
- Recommendation
- Sources
- Limitations
- Confidence

For the question "Which bank appears riskier?", avoid unsupported definitive claims.
Prefer language like:
"Based on the retrieved evidence, Commerzbank appears to have higher uncertainty in this comparison because the kept evidence is weaker or missing in some categories. However, this is not a definitive risk ranking."

Return only valid JSON with this schema:
{{
  "passed": true,
  "issues": [
    {{
      "type": "overclaiming",
      "severity": "medium",
      "message": "Short issue description."
    }}
  ],
  "improved_answer": "The revised final answer.",
  "critic_summary": "One short summary of the critique."
}}

User question:
{question}

Retrieval plan:
{retrieval_plan}

Retrieved / graded evidence context:
{evidence_context}

Draft answer:
{draft_answer}
"""


def _safe_json_loads(text: str) -> dict[str, Any] | None:
    """Parse a JSON object, including responses wrapped in markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _format_retrieval_plan(retrieval_plan: list[dict] | None) -> str:
    """Create a compact text form of planner tasks for the critic."""
    if not retrieval_plan:
        return "No structured retrieval plan was provided."

    lines = []
    for index, task in enumerate(retrieval_plan, start=1):
        lines.append(
            f"{index}. {task.get('entity', 'unknown')} | "
            f"{task.get('risk_type', 'unknown')} | "
            f"{task.get('search_query', 'unknown')}"
        )
    return "\n".join(lines)


def critique_answer(
    question: str,
    draft_answer: str,
    evidence_context: str | None = None,
    retrieval_plan: list[dict] | None = None,
) -> dict:
    """Review and improve a generated answer without retrieving new evidence."""
    prompt = ChatPromptTemplate.from_template(CRITIC_PROMPT)
    llm = ChatOpenAI(model=CHAT_MODEL, temperature=0.0)
    chain = prompt | llm

    response = chain.invoke(
        {
            "question": question,
            "draft_answer": draft_answer,
            "evidence_context": evidence_context or "No evidence context was provided.",
            "retrieval_plan": _format_retrieval_plan(retrieval_plan),
        }
    )

    parsed = _safe_json_loads(response.content)
    if not parsed:
        return {
            "passed": False,
            "issues": [
                {
                    "type": "critic_parse_error",
                    "severity": "medium",
                    "message": "The critic response could not be parsed as JSON.",
                }
            ],
            "improved_answer": draft_answer,
            "critic_summary": "Critic review failed to parse, so the draft answer was returned unchanged.",
        }

    return {
        "passed": bool(parsed.get("passed", False)),
        "issues": parsed.get("issues", []),
        "improved_answer": parsed.get("improved_answer") or draft_answer,
        "critic_summary": parsed.get("critic_summary", "No critic summary provided."),
    }
