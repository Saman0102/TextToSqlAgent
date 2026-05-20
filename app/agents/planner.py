"""Planner agent that produces a high level SQL plan."""

from prompts import PLANNER_SYSTEM_PROMPT


class PlannerAgent:
    def __init__(self, llm) -> None:
        self.llm = llm

    def run(self, user_query: str, schema: str, conversation_context: str = "") -> str:
        user_prompt = (
            "Recent conversation context:\n"
            f"{conversation_context or 'None'}\n\n"
            "User query:\n"
            f"{user_query}\n\n"
            "Ranked schema context:\n"
            f"{schema}\n"
        )
        return self.llm.generate(PLANNER_SYSTEM_PROMPT, user_prompt)
