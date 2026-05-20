"""SQL generator that returns JSON with SQL and params."""

import json
import re

from app.core.config import settings
from app.prompts import SQL_GENERATOR_SYSTEM_PROMPT
from app.core.audit import log_audit


class SQLGeneratorAgent:
    def __init__(self, llm) -> None:
        self.llm = llm

    def run(
        self,
        user_query: str,
        plan: str,
        schema: str,
        error_feedback: str = "",
        conversation_context: str = "",
        audit_id: str | None = None,
    ) -> dict:
        system_prompt = SQL_GENERATOR_SYSTEM_PROMPT.format(max_rows=settings.max_rows)
        user_prompt = (
            "Recent conversation context:\n"
            f"{conversation_context or 'None'}\n\n"
            "User query:\n"
            f"{user_query}\n\n"
            "Plan:\n"
            f"{plan}\n\n"
            "Ranked schema context:\n"
            f"{schema}\n\n"
            "Validation feedback (if any):\n"
            f"{error_feedback}\n"
        )
        try:
            log_audit("prompt", {"phase": "generator", "system": system_prompt[:2000], "user": user_prompt[:4000]}, audit_id=audit_id)
        except Exception:
            pass

        response = self.llm.generate(system_prompt, user_prompt)
        return self._parse_response(response)

    def _parse_response(self, response: str) -> dict:
        text = response.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
            else:
                return {"sql": text, "params": {}}

        sql = str(data.get("sql", "")).strip()
        params = data.get("params", {})
        if not isinstance(params, dict):
            params = {}
        return {"sql": sql, "params": params}
