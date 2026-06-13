"""Planner agent and rule-based question decomposition.

The ``PlannerAgent`` produces a high-level SQL plan via LLM. Rule-based
``decompose_question`` helpers (merged from ``app/decompose.py``) support the
/decompose API and legacy tooling.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from app.core.schema import DEFAULT_SCHEMA_PATH, load_schema
from app.prompts import PLANNER_SYSTEM_PROMPT
from app.core.audit import log_audit


class PlannerAgent:
    def __init__(self, llm) -> None:
        self.llm = llm

    def run(self, user_query: str, schema: str, conversation_context: str = "", audit_id: str | None = None) -> str:
        user_prompt = (
            "Recent conversation context:\n"
            f"{conversation_context or 'None'}\n\n"
            "User query:\n"
            f"{user_query}\n\n"
            "Ranked schema context:\n"
            f"{schema}\n"
        )
        try:
            log_audit(
                "prompt",
                {"phase": "planner", "system": PLANNER_SYSTEM_PROMPT[:2000], "user": user_prompt[:4000]},
                audit_id=audit_id,
            )
        except Exception:
            pass
        return self.llm.generate(PLANNER_SYSTEM_PROMPT, user_prompt)


# --- Rule-based decomposition (merged from app/decompose.py) ---

STOPWORDS = {
    "the", "a", "an", "of", "in", "from", "to", "for", "by", "on", "with", "and",
    "how", "many", "what", "which", "is", "are", "show", "list", "find",
}

DEFAULT_COUNT_COLUMNS = {
    "customers": "customerNumber",
    "orders": "orderNumber",
    "orderdetails": "orderNumber",
    "employees": "employeeNumber",
    "offices": "officeCode",
    "products": "productCode",
    "productlines": "productLine",
    "payments": "checkNumber",
}


def normalize_token(token: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", token.lower())


def guess_nouns(question: str) -> List[str]:
    tokens = re.findall(r"\w+", question.lower())
    candidates = [token for token in tokens if token not in STOPWORDS and not token.isdigit()]
    seen: set[str] = set()
    nouns: List[str] = []
    for token in candidates:
        if token not in seen:
            seen.add(token)
            nouns.append(token)
    return nouns


def detect_intent(question: str) -> str:
    lowered = question.lower()
    if re.search(r"\bhow many\b|\bcount\b|\bnumber of\b", lowered):
        return "Count" + (" (aggregate)" if "per" not in lowered else " (grouped count)")
    if re.search(r"\b(total|sum|average|avg|mean|max|min)\b", lowered):
        match = re.search(r"\b(total|sum|average|avg|mean|max|min)\b", lowered)
        return match.group(1).capitalize() if match else "Aggregate"
    if re.search(r"\b(list|show|get|find)\b", lowered):
        return "Retrieve rows"
    if re.search(r"\btop\b|\bmost\b|\bfewest\b", lowered):
        return "Top-K / ranking"
    return "Unknown intent"


def extract_filters(
    question: str,
    schema: Optional[Dict[str, List[str]]] = None,
    tables: Optional[List[str]] = None,
) -> Optional[List[str]]:
    filters: List[str] = []
    match = re.search(r"country\s*=\s*'?(\w[\w\s-]*)'?", question, re.IGNORECASE)
    if match:
        filters.append(f"country = '{match.group(1).strip()}'")

    from_match = re.search(r"from\s+the\s+([A-Za-z0-9\s-]+)", question, re.IGNORECASE)
    if from_match:
        value = from_match.group(1).strip()
        if schema and any(
            "country" in [normalize_token(column) for column in columns]
            for columns in schema.values()
        ):
            filters.append(f"country = '{value}'")
        else:
            filters.append(f"location/country = '{value}'")

    after_match = re.search(r"after\s+(\d{4})", question)
    if after_match:
        filters.append(f"date > '{after_match.group(1)}-01-01'")
    before_match = re.search(r"before\s+(\d{4})", question)
    if before_match:
        filters.append(f"date < '{before_match.group(1)}-01-01'")

    return filters or None


def find_tables_and_columns(
    question: str,
    schema: Optional[Dict[str, List[str]]],
) -> Tuple[List[str], List[str]]:
    nouns = guess_nouns(question)
    tables: List[str] = []
    columns: List[str] = []
    if schema:
        norm_schema = {normalize_token(table): (table, cols) for table, cols in schema.items()}
        for noun in nouns:
            key = normalize_token(noun)
            if key in norm_schema:
                tables.append(norm_schema[key][0])
            else:
                for table, cols in schema.items():
                    for column in cols:
                        if key == normalize_token(column) or (
                            key and key in normalize_token(column) and key not in STOPWORDS
                        ):
                            columns.append(column)
                            if table not in tables:
                                tables.append(table)
    else:
        return [], []

    return list(dict.fromkeys(tables)), list(dict.fromkeys(columns))


def choose_default_count_columns(
    tables: List[str],
    schema: Optional[Dict[str, List[str]]],
) -> List[str]:
    columns: List[str] = []
    for table in tables:
        if table == "unknown":
            continue
        default_column = DEFAULT_COUNT_COLUMNS.get(table)
        if schema and table in schema:
            table_columns = schema[table]
            if default_column and default_column in table_columns:
                columns.append(default_column)
            elif table_columns:
                columns.append(table_columns[0])
        elif default_column:
            columns.append(default_column)
    return list(dict.fromkeys(columns))


def decompose_question(
    question: str,
    schema_path: Optional[str] = None,
    schema: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Optional[List[str]]]:
    """Rule-based decomposition used by the /decompose API."""
    if schema is None:
        schema_path = schema_path or str(DEFAULT_SCHEMA_PATH)
    if schema is None and schema_path:
        try:
            schema = load_schema(schema_path)
        except Exception:
            schema = None

    intent = detect_intent(question)
    tables, columns = find_tables_and_columns(question, schema)
    filters = extract_filters(question, schema=schema, tables=tables)

    joins = None
    if len(tables) > 1:
        joins = [
            f"{tables[i]} JOIN {tables[j]} ON <join-condition>"
            for i in range(len(tables))
            for j in range(i + 1, len(tables))
        ]

    if not tables:
        tables = ["unknown"]
    if not columns and intent.startswith("Count"):
        columns = choose_default_count_columns(tables, schema)
    if not columns:
        columns = ["unknown"]

    return {
        "Intent": intent,
        "Tables": tables,
        "Columns": columns,
        "Filters": filters,
        "Joins": joins,
    }
