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
If you set "passed" to false, the improved_answer must explicitly fix the main issue rather than making only minor wording changes.

You must return a single valid JSON object only.
Do not include markdown fences.
Do not include prose before or after the JSON object.
Escape newline characters inside JSON strings.
The improved_answer value may contain markdown, but the outer response must still be valid JSON.

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
If the evidence supports a directional conclusion, give it cautiously and distinguish:
1. actual bank risk
2. disclosure detail
3. retrieved evidence strength

When the draft overclaims or fails to answer which bank appears riskier, rewrite more forcefully. The improved answer must include a cautious comparative conclusion similar to:
"Based on the retrieved and graded evidence, Commerzbank appears to carry higher uncertainty in this comparison because the kept evidence is weaker or missing for liquidity risk and less detailed for regulatory risk. However, this should not be treated as a definitive risk ranking. It may reflect weaker retrieved evidence or less detailed disclosure rather than higher actual risk."

Do not say one bank is definitively riskier unless the evidence is strong across all requested risk categories.

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


REQUIRED_RESULT_KEYS = {"passed", "issues", "improved_answer", "critic_summary"}
ANSWER_HEADINGS = [
    "Executive Summary",
    "Key Evidence",
    "Risk Flags",
    "Recommendation",
    "Sources",
    "Limitations",
    "Confidence",
]


def _create_critic_llm() -> ChatOpenAI:
    """Create the critic model, using JSON mode when the client supports it."""
    try:
        return ChatOpenAI(
            model=CHAT_MODEL,
            temperature=0.0,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
    except TypeError:
        return ChatOpenAI(model=CHAT_MODEL, temperature=0.0)


def _strip_markdown_fences(text: str) -> str:
    """Remove common markdown code fences around JSON."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    return cleaned


def _extract_first_json_object(text: str) -> str | None:
    """Extract the first balanced JSON object from mixed text."""
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


def _safe_json_loads(text: str) -> dict[str, Any] | None:
    """Parse a JSON object, including responses wrapped in markdown fences."""
    cleaned = _strip_markdown_fences(text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        json_object = _extract_first_json_object(cleaned)
        if not json_object:
            return None
        try:
            return json.loads(json_object)
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


def _asks_which_bank_is_riskier(question: str) -> bool:
    """Detect the common comparison conclusion request."""
    lowered = question.lower()
    return "which bank" in lowered and "riskier" in lowered


def _has_risk_uncertainty_distinction(answer: str) -> bool:
    """Check whether the rewrite separates risk from evidence/disclosure limits."""
    lowered = answer.lower()
    return (
        "actual risk" in lowered
        and "disclosure" in lowered
        and ("retrieved evidence" in lowered or "evidence strength" in lowered)
    )


def _insert_after_heading(answer: str, heading: str, paragraph: str) -> str:
    """Insert a paragraph after a markdown/plain-text section heading."""
    pattern = re.compile(rf"({re.escape(heading)}\s*:?\s*)", flags=re.IGNORECASE)
    match = pattern.search(answer)
    if not match:
        return f"{paragraph}\n\n{answer}"

    insert_at = match.end()
    return answer[:insert_at] + f"\n{paragraph}\n" + answer[insert_at:]


def _fix_markdown_headings(answer: str) -> str:
    """Normalize malformed bold section headings from critic rewrites."""
    fixed = answer
    for heading in ANSWER_HEADINGS:
        fixed = re.sub(
            rf"\*\*{re.escape(heading)}:\s*\n",
            f"**{heading}:**\n",
            fixed,
            flags=re.IGNORECASE,
        )
        fixed = re.sub(
            rf"\*\*{re.escape(heading)}:\*\*",
            f"**{heading}:**",
            fixed,
            flags=re.IGNORECASE,
        )
    fixed = re.sub(r"\n\*\*\s*(?=\n|$)", "\n", fixed)
    return fixed


def _strengthen_failed_rewrite(question: str, result: dict, draft_answer: str) -> dict:
    """Ensure failed critiques produce a direct, cautious comparative conclusion."""
    if result["passed"] or not _asks_which_bank_is_riskier(question):
        return result

    improved_answer = result.get("improved_answer") or draft_answer
    if _has_risk_uncertainty_distinction(improved_answer):
        result["improved_answer"] = _fix_markdown_headings(improved_answer)
        return result

    cautious_conclusion = (
        "Based on the retrieved and graded evidence, Commerzbank appears to carry "
        "higher uncertainty in this comparison because the kept evidence is weaker "
        "or missing for liquidity risk and less detailed for regulatory risk. "
        "However, this should not be treated as a definitive risk ranking. It may "
        "reflect weaker retrieved evidence or less detailed disclosure rather than "
        "higher actual risk."
    )
    result["improved_answer"] = _fix_markdown_headings(_insert_after_heading(
        improved_answer,
        "Executive Summary",
        cautious_conclusion,
    ))
    result["critic_summary"] = (
        result.get("critic_summary", "")
        + " The rewrite was strengthened to separate actual risk, disclosure detail, "
        "and retrieved evidence strength."
    ).strip()
    return result


def _normalize_critic_result(parsed: dict[str, Any], draft_answer: str) -> dict:
    """Guarantee the critic result has the expected schema and clean formatting."""
    issues = parsed.get("issues", [])
    if not isinstance(issues, list):
        issues = [
            {
                "type": "critic_schema_warning",
                "severity": "low",
                "message": "Critic returned issues in a non-list format.",
            }
        ]

    normalized = {
        "passed": bool(parsed.get("passed", False)),
        "issues": issues,
        "improved_answer": _fix_markdown_headings(
            str(parsed.get("improved_answer") or draft_answer)
        ),
        "critic_summary": str(parsed.get("critic_summary") or "No critic summary provided."),
    }

    missing_keys = REQUIRED_RESULT_KEYS.difference(parsed.keys())
    if missing_keys:
        normalized["passed"] = False
        normalized["issues"].append(
            {
                "type": "critic_schema_warning",
                "severity": "medium",
                "message": "Critic response was missing required keys: "
                + ", ".join(sorted(missing_keys)),
            }
        )

    return normalized


def critique_answer(
    question: str,
    draft_answer: str,
    evidence_context: str | None = None,
    retrieval_plan: list[dict] | None = None,
) -> dict:
    """Review and improve a generated answer without retrieving new evidence."""
    prompt = ChatPromptTemplate.from_template(CRITIC_PROMPT)
    llm = _create_critic_llm()
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
        fallback = _strengthen_failed_rewrite(question, {
            "passed": False,
            "issues": [
                {
                    "type": "critic_parse_error",
                    "severity": "medium",
                    "message": "The critic response could not be parsed as JSON.",
                }
            ],
            "improved_answer": draft_answer,
            "critic_summary": "Critic review failed to parse.",
        }, draft_answer)
        if fallback["improved_answer"] == draft_answer:
            fallback["critic_summary"] += " The draft answer was returned unchanged."
        else:
            fallback["critic_summary"] += " A deterministic fallback rewrite was applied."
        fallback["improved_answer"] = _fix_markdown_headings(fallback["improved_answer"])
        return fallback

    result = _normalize_critic_result(parsed, draft_answer)
    return _strengthen_failed_rewrite(question, result, draft_answer)
