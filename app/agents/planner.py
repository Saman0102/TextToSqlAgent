"""Planner agent that produces a high level SQL plan."""

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
            # truncate prompts to avoid huge logs
            log_audit("prompt", {"phase": "planner", "system": PLANNER_SYSTEM_PROMPT[:2000], "user": user_prompt[:4000]}, audit_id=audit_id)
        except Exception:
            pass
        return self.llm.generate(PLANNER_SYSTEM_PROMPT, user_prompt)
