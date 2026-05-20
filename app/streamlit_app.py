"""Streamlit chat UI for the Text-to-SQL agent."""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.graph.workflow import run_workflow

AUDIT_LOG_PATH = APP_DIR / "logs" / "query_audit.jsonl"


def _load_recent_audit_entries(audit_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    if not audit_id or not AUDIT_LOG_PATH.exists():
        return []

    entries: List[Dict[str, Any]] = []
    try:
        with AUDIT_LOG_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("audit_id") == audit_id:
                    entries.append(record)
    except Exception:
        return []

    return entries[-limit:]

st.set_page_config(page_title="Text-to-SQL Agent", layout="centered")

st.title("Text-to-SQL Agent")
st.caption("Ask a question about the database and the agent will plan, generate, validate, and execute SQL.")

if "messages" not in st.session_state:
    st.session_state.messages = []

example_queries = [
    "List the top 10 customers by total payments.",
    "Show orders with the shipped date and status for 2005.",
    "Which product lines have the highest average MSRP?",
]

with st.container(border=True):
    st.subheader("Try one of these examples")
    columns = st.columns(len(example_queries))
    for index, example_query in enumerate(example_queries):
        if columns[index].button(example_query, use_container_width=True):
            st.session_state.example_prompt = example_query

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

default_prompt = st.session_state.pop("example_prompt", "")
prompt = st.chat_input("Ask a question about the database", key="chat_input", disabled=False)
prompt_to_run = prompt or default_prompt

if prompt_to_run:
    conversation_history = st.session_state.messages[-6:]
    st.session_state.messages.append({"role": "user", "content": prompt_to_run})
    with st.chat_message("user"):
        st.markdown(prompt_to_run)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            state = run_workflow(prompt_to_run, conversation_history=conversation_history)
        st.markdown(state.final_answer or "No answer returned.")
        st.markdown(f"**Audit ID:** {state.audit_id}")
        with st.expander("Details"):
            st.write(
                {
                    "plan": state.plan,
                    "conversation_context": state.conversation_context,
                    "ranked_schema_context": state.ranked_schema_context,
                    "sql": state.generated_sql,
                    "params": state.sql_params,
                    "errors": state.errors,
                    "audit_id": state.audit_id,
                }
            )
            if st.button("Show audit trail for this run", key=f"audit-trail-{state.audit_id}"):
                st.write(f"Showing recent entries from {AUDIT_LOG_PATH}")
                st.json(_load_recent_audit_entries(state.audit_id))

    st.session_state.messages.append(
        {"role": "assistant", "content": state.final_answer or "No answer returned."}
    )
