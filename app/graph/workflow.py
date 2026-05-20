"""Agentic workflow orchestration."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents import ExecutorAgent, LLMClient, PlannerAgent, SQLGeneratorAgent, SQLValidator, SummarizerAgent
from app.core.audit import log_audit, make_audit_id
from app.core.config import SECRETS_PATHS, SETTINGS_PATH, settings
from app.core.schema_context import SchemaMetadata, build_ranked_schema_context, load_schema_metadata


@dataclass
class WorkflowState:
    user_query: str
    audit_id: str = ""
    conversation_context: str = ""
    ranked_schema_context: str = ""
    plan: str = ""
    generated_sql: str = ""
    sql_params: Dict[str, Any] = field(default_factory=dict)
    is_valid_sql: bool = False
    execution_results: Optional[List[Dict[str, Any]]] = None
    final_answer: str = ""
    errors: List[str] = field(default_factory=list)


def _load_schema() -> str:
    schema_path = Path(__file__).resolve().parents[1] / "sql" / "seed.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    return schema_path.read_text(encoding="utf-8")


def _load_schema_metadata() -> SchemaMetadata:
    schema_path = Path(__file__).resolve().parents[1] / "sql" / "seed.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    return load_schema_metadata(schema_path)


def _format_conversation_context(conversation_history: Optional[List[Dict[str, str]]], max_turns: int = 6) -> str:
    if not conversation_history:
        return ""

    recent_messages = conversation_history[-max_turns:]
    lines: List[str] = []
    for message in recent_messages:
        role = str(message.get("role", "")).strip().lower() or "unknown"
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        if role not in {"user", "assistant", "system"}:
            role = "user"
        lines.append(f"{role.title()}: {content}")
    return "\n".join(lines)


def run_workflow(
    user_query: str,
    max_attempts: int = 3,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> WorkflowState:
    audit_id = make_audit_id()
    state = WorkflowState(
        user_query=user_query,
        audit_id=audit_id,
        conversation_context=_format_conversation_context(conversation_history),
    )
    try:
        schema = _load_schema()
        schema_metadata = _load_schema_metadata()
        state.ranked_schema_context = build_ranked_schema_context(
            question=user_query,
            conversation_context=state.conversation_context,
            metadata=schema_metadata,
        )
    except Exception as exc:
        state.errors.append(f"Schema load error: {exc}")
        return state

    llm = LLMClient()
    planner = PlannerAgent(llm)
    generator = SQLGeneratorAgent(llm)
    validator = SQLValidator()
    executor = ExecutorAgent()
    summarizer = SummarizerAgent(llm)

    try:
        state.plan = planner.run(user_query, state.ranked_schema_context or schema, state.conversation_context, audit_id=state.audit_id)
    except Exception as exc:
        state.errors.append(f"Planner error: {exc}")
        state.errors.append(
            "Config diagnostics: "
            f"settings={SETTINGS_PATH}, "
            f"secrets={[str(p) for p in SECRETS_PATHS]}, "
            f"provider={settings.llm_provider}, "
            f"model={settings.gemini_model}, "
            f"key_loaded={bool(settings.gemini_api_key)}"
        )
        return state

    feedback = ""
    for attempt in range(max_attempts):
        gen = generator.run(
            user_query,
            state.plan,
            state.ranked_schema_context or schema,
            feedback,
            state.conversation_context,
            audit_id=state.audit_id,
        )
        state.generated_sql = gen.get("sql", "")
        state.sql_params = gen.get("params", {})
        try:
            log_audit(
                "generation",
                {
                    "sql": state.generated_sql,
                    "params": state.sql_params,
                    "attempt": attempt + 1,
                },
                audit_id=state.audit_id,
            )
        except Exception:
            pass

        validation = validator.validate(state.generated_sql, audit_id=state.audit_id)
        state.is_valid_sql = validation.is_valid
        if state.is_valid_sql:
            break

        feedback = validation.message
        state.errors.append(f"Validator error: {validation.message}")

    if not state.is_valid_sql:
        state.final_answer = "Unable to produce a valid read-only SQL query."
        return state

    try:
        state.execution_results = executor.run(state.generated_sql, state.sql_params)
        # audit successful execution
        try:
            log_audit(
                "execution",
                {
                    "sql": state.generated_sql,
                    "params": state.sql_params,
                    "rows": len(state.execution_results) if state.execution_results is not None else 0,
                },
                audit_id=state.audit_id,
            )
        except Exception:
            pass
    except Exception as exc:
        state.errors.append(f"Execution error: {exc}")
        try:
            log_audit(
                "execution",
                {"sql": state.generated_sql, "params": state.sql_params, "error": str(exc)},
                audit_id=state.audit_id,
            )
        except Exception:
            pass
        state.final_answer = "Query execution failed."
        return state

    try:
        state.final_answer = summarizer.run(user_query, state.execution_results, state.conversation_context, audit_id=state.audit_id)
        try:
            log_audit(
                "summarizer",
                {
                    "rows": len(state.execution_results) if state.execution_results is not None else 0,
                    "answer": state.final_answer,
                },
                audit_id=state.audit_id,
            )
        except Exception:
            pass
    except Exception as exc:
        state.errors.append(f"Summarizer error: {exc}")
        state.final_answer = "Summarization failed."
        try:
            log_audit(
                "summarizer",
                {"rows": len(state.execution_results) if state.execution_results is not None else 0, "error": str(exc)},
                audit_id=state.audit_id,
            )
        except Exception:
            pass

    return state
