"""Deterministic V1 query planner for structured finance retrieval."""

from __future__ import annotations


ENTITY_PATTERNS = {
    "Deutsche Bank": ["deutsche bank", "deutsche"],
    "Commerzbank": ["commerzbank", "commerz"],
    "EBA": ["eba", "european banking authority"],
}

RISK_TYPE_PATTERNS = {
    "operational risk": ["operational risk", "operations risk", "operational"],
    "liquidity risk": ["liquidity risk", "funding risk", "liquidity"],
    "regulatory risk": ["regulatory risk", "regulation risk", "supervisory risk", "regulatory"],
}

DEFAULT_COMPARISON_RISKS = [
    "operational risk",
    "liquidity risk",
    "regulatory risk",
]


def detect_entities(question: str) -> list[str]:
    """Detect supported entities in question order."""
    lowered = question.lower()
    entities = []
    for entity, patterns in ENTITY_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            entities.append(entity)
    return entities


def detect_risk_types(question: str) -> list[str]:
    """Detect supported risk dimensions in a deterministic order."""
    lowered = question.lower()
    risk_types = []
    for risk_type, patterns in RISK_TYPE_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            risk_types.append(risk_type)
    return risk_types


def is_bank_comparison(question: str, entities: list[str]) -> bool:
    """Return True for the V1 Deutsche Bank vs Commerzbank comparison pattern."""
    lowered = question.lower()
    required_entities = {"Deutsche Bank", "Commerzbank"}
    return "compare" in lowered and required_entities.issubset(set(entities))


def purpose_for(entity: str, risk_type: str) -> str:
    """Create a short retrieval purpose for the task."""
    if entity == "EBA":
        return "Retrieve regulatory context for banking supervision and risk comparison."
    if risk_type == "liquidity risk":
        return f"Retrieve evidence about {entity}'s liquidity position and funding risk."
    return f"Retrieve evidence about {entity}'s {risk_type} exposure."


def plan_query(question: str) -> list[dict]:
    """Create structured retrieval tasks for a finance question.

    This V1 planner is intentionally rule-based and deterministic. It is shaped
    like an agent planning module so it can later be replaced by an LLM planner.
    """
    entities = detect_entities(question)
    risk_types = detect_risk_types(question)

    if is_bank_comparison(question, entities):
        comparison_entities = ["Deutsche Bank", "Commerzbank"]
        if not risk_types:
            risk_types = DEFAULT_COMPARISON_RISKS

        tasks = []
        for entity in comparison_entities:
            for risk_type in risk_types:
                tasks.append(
                    {
                        "entity": entity,
                        "risk_type": risk_type,
                        "search_query": f"{entity} {risk_type}",
                        "purpose": purpose_for(entity, risk_type),
                    }
                )

        if "regulatory risk" in risk_types:
            tasks.append(
                {
                    "entity": "EBA",
                    "risk_type": "regulatory context",
                    "search_query": "EBA regulatory context banking supervision",
                    "purpose": purpose_for("EBA", "regulatory context"),
                }
            )

        return tasks

    tasks = []
    if risk_types:
        for entity in entities or ["General"]:
            for risk_type in risk_types:
                search_query = f"{entity} {risk_type}" if entity != "General" else risk_type
                tasks.append(
                    {
                        "entity": entity,
                        "risk_type": risk_type,
                        "search_query": search_query,
                        "purpose": purpose_for(entity, risk_type),
                    }
                )

    return tasks
