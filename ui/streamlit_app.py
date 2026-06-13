import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests
import streamlit as st

# Config backend URL
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Paths for evaluation CSVs
UI_ROOT = Path(__file__).resolve().parent
QUESTIONS_ONLY_PATH = UI_ROOT.parent / "evaluation" / "questions_only.csv"
QUESTIONS_WITH_ANSWERS_PATH = UI_ROOT.parent / "evaluation" / "questions_and_answers.csv"


def _load_questions(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    data = pd.read_csv(path)
    if "question" not in data.columns:
        raise ValueError("CSV must include a question column")
    data["question"] = data["question"].astype(str).str.strip()
    data = data[data["question"].str.len() > 0]
    return data


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item is not None)
    return str(value)


def _flatten_decomposition(decomp: Dict[str, Any]) -> Dict[str, str]:
    return {
        "intent": _format_value(decomp.get("Intent") or decomp.get("intent")),
        "tables": _format_value(decomp.get("Tables") or decomp.get("tables")),
        "columns": _format_value(decomp.get("Columns") or decomp.get("columns")),
        "filters": _format_value(decomp.get("Filters") or decomp.get("filters")),
        "joins": _format_value(decomp.get("Joins") or decomp.get("joins")),
    }


def _decompose_questions(questions: List[str]) -> pd.DataFrame:
    rows: List[Dict[str, str]] = []
    for question in questions:
        entry: Dict[str, str] = {"question": question}
        try:
            response = requests.get(f"{BACKEND_URL}/decompose", params={"question": question})
            response.raise_for_status()
            decomp = response.json()
            entry.update(_flatten_decomposition(decomp))
            exception_message = ""
        except Exception as exc:
            exception_message = str(exc)
            entry.update({"intent": "", "tables": "", "columns": "", "filters": "", "joins": ""})
        entry["error"] = exception_message
        rows.append(entry)
    return pd.DataFrame(rows)


st.set_page_config(page_title="Text-to-SQL Agentic Pipeline", layout="wide")

st.title("🤖 Text-to-SQL Agentic Pipeline")
st.caption("A premium AI assistant that plans, generates, validates, and executes SQL queries.")

# Use tabs to organize Chat and Batch tools
tab1, tab2 = st.tabs(["💬 Interactive Chat", "📊 Batch Decomposition"])

with tab1:
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
            if message.get("sql"):
                st.code(message["sql"], language="sql")
            res = message.get("result")
            if res is not None:
                if isinstance(res, list) and len(res) > 0:
                    df = pd.DataFrame(res)
                    st.dataframe(df, use_container_width=True)
                elif not isinstance(res, list):
                    st.write(f"**Result:** `{res}`")
            if message.get("status"):
                audit_id = message.get('audit_id')
                caption = f"Status: {message['status']}"
                if audit_id:
                    caption += f" | Audit ID: {audit_id}"
                st.caption(caption)

    default_prompt = st.session_state.pop("example_prompt", "")
    prompt = st.chat_input("Ask a question about the database", key="chat_input")
    prompt_to_run = prompt or default_prompt

    if prompt_to_run:
        conversation_history = []
        for msg in st.session_state.messages[-6:]:
            conversation_history.append({"role": msg["role"], "content": msg["content"]})

        st.session_state.messages.append({"role": "user", "content": prompt_to_run})
        with st.chat_message("user"):
            st.markdown(prompt_to_run)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    payload = {
                        "question": prompt_to_run,
                        "conversation_history": conversation_history,
                    }
                    response = requests.post(f"{BACKEND_URL}/agent/sql", json=payload)
                    response.raise_for_status()
                    data = response.json()
                except Exception as exc:
                    data = {
                        "summary": f"Error communicating with backend: {exc}",
                        "sql": "",
                        "result": [],
                        "status": "failed",
                        "audit_id": "",
                        "plan": "",
                        "conversation_context": "",
                        "ranked_schema_context": "",
                        "errors": [str(exc)],
                    }

            st.markdown(data.get("summary") or "No answer returned.")
            if data.get("sql"):
                st.code(data["sql"], language="sql")
            res = data.get("result")
            if res is not None:
                if isinstance(res, list) and len(res) > 0:
                    df = pd.DataFrame(res)
                    st.dataframe(df, use_container_width=True)
                elif not isinstance(res, list):
                    st.write(f"**Result:** `{res}`")
            
            audit_id = data.get('audit_id')
            caption = f"Status: {data.get('status')}"
            if audit_id:
                caption += f" | Audit ID: {audit_id}"
            st.caption(caption)

            if any(k in data for k in ["plan", "conversation_context", "ranked_schema_context", "params", "errors", "audit_id"]):
                with st.expander("Show Execution Details"):
                    st.write(
                        {
                            "plan": data.get("plan"),
                            "conversation_context": data.get("conversation_context"),
                            "ranked_schema_context": data.get("ranked_schema_context"),
                            "sql": data.get("sql"),
                            "params": data.get("params"),
                            "errors": data.get("errors"),
                            "audit_id": data.get("audit_id"),
                        }
                    )
                if data.get("audit_id"):
                    if st.button(
                        "Show audit trail for this run",
                        key=f"audit-trail-{data.get('audit_id')}",
                    ):
                        try:
                            audit_resp = requests.get(
                                f"{BACKEND_URL}/agent/audit/{data.get('audit_id')}"
                            )
                            audit_resp.raise_for_status()
                            st.json(audit_resp.json())
                        except Exception as e:
                            st.error(f"Failed to fetch audit trail: {e}")

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": data.get("summary") or "No answer returned.",
                "sql": data.get("sql"),
                "result": data.get("result"),
                "status": data.get("status"),
                "audit_id": data.get("audit_id"),
            }
        )

with tab2:
    st.header("Batch decomposition (CSV)")
    st.caption("Runs Gemini decomposition for each question in the selected CSV.")

    dataset_options: List[Dict[str, object]] = []
    if QUESTIONS_ONLY_PATH.exists():
        dataset_options.append({"label": "questions_only.csv", "path": QUESTIONS_ONLY_PATH})
    if QUESTIONS_WITH_ANSWERS_PATH.exists():
        dataset_options.append(
            {"label": "questions_and_answers.csv", "path": QUESTIONS_WITH_ANSWERS_PATH}
        )

    if not dataset_options:
        st.warning(
            "No questions CSV files were found. Place them in the `evaluation/` directory."
        )
    else:
        labels = [option["label"] for option in dataset_options]
        selected_label = st.selectbox("Choose a dataset", labels, index=0)
        selected_option = next(
            option for option in dataset_options if option["label"] == selected_label
        )

        try:
            df_questions = _load_questions(selected_option["path"])
        except Exception as exc:
            st.error(f"Failed to load questions: {exc}")
            df_questions = pd.DataFrame()

        max_rows = len(df_questions) if not df_questions.empty else 0
        limit = st.number_input(
            "Max questions",
            min_value=1,
            max_value=max_rows or 1,
            value=min(20, max_rows or 1),
            step=1,
        )

        if "batch_decomposition" not in st.session_state:
            st.session_state.batch_decomposition = None
        if "batch_key" not in st.session_state:
            st.session_state.batch_key = None

        if st.button("Run batch decomposition") and not df_questions.empty:
            with st.spinner("Running decomposition for selected questions..."):
                questions = df_questions["question"].head(int(limit)).tolist()
                results = _decompose_questions(questions)
                if "answer" in df_questions.columns:
                    answers = df_questions["answer"].head(int(limit)).tolist()
                    results.insert(1, "expected_sql", answers)
                st.session_state.batch_decomposition = results
                st.session_state.batch_key = f"{selected_label}:{limit}"

        if st.session_state.batch_decomposition is not None:
            st.subheader("Decomposition results")
            st.dataframe(st.session_state.batch_decomposition, use_container_width=True)
