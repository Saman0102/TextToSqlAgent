"""Summarizer agent that converts rows into natural language."""

import json

from app.prompts import SUMMARIZER_SYSTEM_PROMPT
from app.core.audit import log_audit


class SummarizerAgent:
    def __init__(self, llm) -> None:
        self.llm = llm

    def run(self, user_query: str, results: list[dict], conversation_context: str = "", audit_id: str | None = None) -> str:
        if not results:
            return "No results found for that query."

        data = json.dumps(results, ensure_ascii=True, default=str)
        user_prompt = (
            "Recent conversation context:\n"
            f"{conversation_context or 'None'}\n\n"
            "User query:\n"
            f"{user_query}\n\n"
            "Results (JSON rows):\n"
            f"{data}\n"
        )
        try:
            log_audit("prompt", {"phase": "summarizer", "system": SUMMARIZER_SYSTEM_PROMPT[:2000], "user": user_prompt[:4000]}, audit_id=audit_id)
        except Exception:
            pass
        return self.llm.generate(SUMMARIZER_SYSTEM_PROMPT, user_prompt)
