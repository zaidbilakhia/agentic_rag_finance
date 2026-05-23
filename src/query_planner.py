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

QUESTION_TYPE_MISSING_EVIDENCE = "missing_evidence"
QUESTION_TYPE_BANK_COMPARISON = "bank_comparison"
QUESTION_TYPE_SINGLE_RISK_COMPARISON = "single_risk_comparison"
QUESTION_TYPE_SINGLE_BANK = "single_bank"
QUESTION_TYPE_EBA_CONTEXT = "eba_context"
QUESTION_TYPE_GENERAL = "general"


RISK_TASK_TEMPLATES = {
    "liquidity risk": [
        ("liquidity risk management framework", "Retrieve evidence about liquidity risk governance, policies, and management framework."),
        ("short-term liquidity risk", "Retrieve evidence about short-term liquidity risk and payment obligations."),
        ("structural funding risk", "Retrieve evidence about structural funding, refinancing, and funding risk."),
        ("liquidity stress testing", "Retrieve evidence about liquidity stress testing and stress scenarios."),
        ("LCR NSFR funding ratios", "Retrieve evidence about LCR, NSFR, and funding ratio disclosures."),
        ("liquidity risk flags", "Retrieve evidence about liquidity risk flags and areas requiring further diligence."),
    ],
    "operational risk": [
        ("operational risk strategy", "Retrieve evidence about operational risk strategy and priorities."),
        ("operational risk management framework", "Retrieve evidence about the operational risk management framework."),
        ("non-financial risk", "Retrieve evidence about non-financial risk connected to operational risk."),
        ("internal controls", "Retrieve evidence about internal controls and control environment."),
        ("operational loss events", "Retrieve evidence about operational losses, incidents, or loss events."),
        ("operational risk flags", "Retrieve evidence about operational risk flags and areas requiring further diligence."),
    ],
    "regulatory risk": [
        ("regulatory risk", "Retrieve evidence about regulatory risk exposure."),
        ("regulatory compliance", "Retrieve evidence about regulatory compliance controls and obligations."),
        ("ECB supervision", "Retrieve evidence about ECB supervision and supervisory expectations."),
        ("BaFin supervision", "Retrieve evidence about BaFin supervision and regulatory oversight."),
        ("capital requirements", "Retrieve evidence about capital requirements and regulatory capital pressure."),
        ("regulatory findings", "Retrieve evidence about regulatory findings, remediation, or enforcement issues."),
    ],
}

MISSING_EVIDENCE_TEMPLATES = {
    "liquidity risk": [
        "liquidity risk",
        "liquidity risk management",
        "LCR NSFR",
    ],
    "operational risk": [
        "operational risk",
        "operational risk management",
        "operational loss events",
    ],
    "regulatory risk": [
        "regulatory risk",
        "regulatory compliance",
        "regulatory findings",
    ],
}


def detect_entities(question: str) -> list[str]:
    """Detect supported entities in question order."""
    lowered = question.lower()
    entities = []
    for entity, patterns in ENTITY_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            entities.append(entity)
    if not entities and any(term in lowered for term in ["two banks", "both banks"]):
        entities.extend(["Deutsche Bank", "Commerzbank"])
    return entities


def detect_risk_types(question: str) -> list[str]:
    """Detect supported risk dimensions in a deterministic order."""
    lowered = question.lower()
    risk_types = []
    for risk_type, patterns in RISK_TYPE_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            risk_types.append(risk_type)
    return risk_types


def detect_question_type(question: str, entities: list[str], risk_types: list[str]) -> str:
    """Classify the question into a deterministic planner route."""
    lowered = question.lower()
    bank_entities = [entity for entity in entities if entity in {"Deutsche Bank", "Commerzbank"}]
    comparison_terms = ["compare", "comparing", "comparison", "versus", " vs ", "against"]
    missing_terms = ["missing", "weak evidence", "weak when", "weak or", "insufficient"]

    if "eba" in lowered or "european banking authority" in lowered:
        if not bank_entities:
            return QUESTION_TYPE_EBA_CONTEXT

    if len(bank_entities) >= 2 and any(term in lowered for term in missing_terms):
        return QUESTION_TYPE_MISSING_EVIDENCE

    if len(bank_entities) >= 2 and any(term in lowered for term in comparison_terms):
        if len(risk_types) == 1:
            return QUESTION_TYPE_SINGLE_RISK_COMPARISON
        return QUESTION_TYPE_BANK_COMPARISON

    if len(bank_entities) == 1 and risk_types:
        return QUESTION_TYPE_SINGLE_BANK

    return QUESTION_TYPE_GENERAL


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


def make_task(entity: str, risk_type: str, search_query: str, purpose: str | None = None) -> dict:
    """Build one planner task with the standard fields."""
    return {
        "entity": entity,
        "risk_type": risk_type,
        "search_query": search_query,
        "purpose": purpose or purpose_for(entity, risk_type),
    }


def build_single_bank_tasks(entity: str, risk_types: list[str]) -> list[dict]:
    """Build expanded task coverage for single-bank, single-risk questions."""
    tasks = []
    for risk_type in risk_types:
        templates = RISK_TASK_TEMPLATES.get(risk_type)
        if not templates:
            tasks.append(make_task(entity, risk_type, f"{entity} {risk_type}"))
            continue

        for query_suffix, purpose_suffix in templates:
            tasks.append(
                make_task(
                    entity=entity,
                    risk_type=risk_type,
                    search_query=f"{entity} {query_suffix}",
                    purpose=purpose_suffix.replace("Retrieve evidence", f"Retrieve evidence for {entity}"),
                )
            )
    return tasks


def build_comparison_tasks(
    entities: list[str],
    risk_types: list[str],
    expanded_single_risk: bool = False,
) -> list[dict]:
    """Build comparison retrieval tasks for two-bank questions."""
    tasks = []
    comparison_entities = [
        entity for entity in ["Deutsche Bank", "Commerzbank"] if entity in entities
    ]
    if not comparison_entities:
        comparison_entities = ["Deutsche Bank", "Commerzbank"]

    for entity in comparison_entities:
        for risk_type in risk_types:
            if expanded_single_risk and risk_type == "regulatory risk":
                tasks.append(make_task(entity, risk_type, f"{entity} regulatory risk"))
                tasks.append(make_task(entity, risk_type, f"{entity} regulatory compliance"))
            else:
                tasks.append(make_task(entity, risk_type, f"{entity} {risk_type}"))

    if "regulatory risk" in risk_types:
        tasks.append(
            make_task(
                "EBA",
                "regulatory context",
                "EBA regulatory context banking supervision",
                purpose_for("EBA", "regulatory context"),
            )
        )
    return tasks


def build_missing_evidence_tasks(entities: list[str], risk_types: list[str]) -> list[dict]:
    """Build targeted tasks for questions about weak or missing evidence."""
    tasks = []
    bank_entities = [entity for entity in ["Commerzbank", "Deutsche Bank"] if entity in entities]
    if not bank_entities:
        bank_entities = ["Commerzbank", "Deutsche Bank"]
    for entity in bank_entities:
        for risk_type in risk_types or DEFAULT_COMPARISON_RISKS:
            for query_suffix in MISSING_EVIDENCE_TEMPLATES.get(risk_type, [risk_type]):
                tasks.append(
                    make_task(
                        entity,
                        risk_type,
                        f"{entity} {query_suffix}",
                        f"Retrieve evidence to assess whether {entity}'s {risk_type} support is strong, weak, or missing.",
                    )
                )
    return tasks


def build_eba_context_tasks() -> list[dict]:
    """Build EBA-focused regulatory context tasks."""
    return [
        make_task(
            "EBA",
            "regulatory context",
            "EBA regulatory context banking supervision",
            purpose_for("EBA", "regulatory context"),
        ),
        make_task(
            "EBA",
            "regulatory context",
            "EBA banking supervision risk management capital liquidity governance",
            "Retrieve EBA context about supervision, risk management, capital, liquidity, and governance.",
        ),
    ]


def plan_query(question: str) -> list[dict]:
    """Create structured retrieval tasks for a finance question.

    This V1 planner is intentionally rule-based and deterministic. It is shaped
    like an agent planning module so it can later be replaced by an LLM planner.
    """
    entities = detect_entities(question)
    risk_types = detect_risk_types(question)
    question_type = detect_question_type(question, entities, risk_types)

    if question_type == QUESTION_TYPE_SINGLE_RISK_COMPARISON:
        return build_comparison_tasks(
            entities,
            risk_types or DEFAULT_COMPARISON_RISKS,
            expanded_single_risk=True,
        )

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

    if question_type == QUESTION_TYPE_MISSING_EVIDENCE:
        return build_missing_evidence_tasks(entities, risk_types)

    if question_type == QUESTION_TYPE_BANK_COMPARISON:
        return build_comparison_tasks(entities, risk_types or DEFAULT_COMPARISON_RISKS)

    if question_type == QUESTION_TYPE_SINGLE_BANK:
        bank_entities = [entity for entity in entities if entity in {"Deutsche Bank", "Commerzbank"}]
        return build_single_bank_tasks(bank_entities[0], risk_types)

    if question_type == QUESTION_TYPE_EBA_CONTEXT:
        return build_eba_context_tasks()

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
