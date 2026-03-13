"""Shared Streamlit UI components."""

import streamlit as st
import pandas as pd
from lib.queries import get_jobs


def _persist_selectbox(label, options, session_key, **kwargs):
    """Selectbox that persists its value in session_state across pages."""
    index = 0
    if session_key in st.session_state:
        try:
            index = options.index(st.session_state[session_key])
        except ValueError:
            index = 0

    def _on_change():
        st.session_state[session_key] = st.session_state[f"_widget_{session_key}"]

    return st.sidebar.selectbox(
        label, options,
        index=index,
        key=f"_widget_{session_key}",
        on_change=_on_change,
        **kwargs,
    )


def _persist_multiselect(label, options, session_key, default=None, **kwargs):
    """Multiselect that persists its value in session_state across pages."""
    if session_key in st.session_state:
        current = [v for v in st.session_state[session_key] if v in options]
    else:
        current = default if default is not None else options

    def _on_change():
        st.session_state[session_key] = st.session_state[f"_widget_{session_key}"]

    return st.sidebar.multiselect(
        label, options,
        default=current,
        key=f"_widget_{session_key}",
        on_change=_on_change,
        **kwargs,
    )


def job_selector(key: str = "job_select", allow_all: bool = True) -> str | None:
    """Sidebar job selector. Returns job_id or None for 'All jobs'."""
    jobs = get_jobs()
    if jobs.empty:
        st.sidebar.warning("No jobs ingested yet. Run `python ingest.py` first.")
        return None

    options = ["All jobs"] + jobs["job_id"].tolist() if allow_all else jobs["job_id"].tolist()
    selected = _persist_selectbox("Job", options, key)
    if selected == "All jobs":
        return None
    return selected


OUTCOME_OPTIONS = ["All", "Passed", "Tests Failed", "Agent Timeout", "Verifier Timeout"]


def outcome_filter(key: str = "outcome_filter") -> str:
    """Sidebar outcome filter. Returns selected outcome or 'All'."""
    return _persist_selectbox("Outcome", OUTCOME_OPTIONS, key)


def job_multiselect(key: str = "job_multiselect") -> list[str]:
    """Sidebar job multiselect. Returns list of selected job_ids."""
    jobs = get_jobs()
    if jobs.empty:
        return []
    options = jobs["job_id"].tolist()
    return _persist_multiselect("Jobs to compare", options, key, default=options)


def apply_outcome_filter(df: pd.DataFrame, outcome: str) -> pd.DataFrame:
    """Filter a DataFrame that has a 'failure_reason' column by outcome."""
    if outcome == "All" or "failure_reason" not in df.columns:
        return df
    return df[df["failure_reason"] == outcome]


def trial_selector(trials_df: pd.DataFrame, key: str = "trial_select") -> str | None:
    """Sidebar trial selector from a given DataFrame."""
    if trials_df.empty:
        return None
    options = trials_df["trial_name"].tolist()
    return _persist_selectbox("Trial", options, key)


def metric_card(label: str, value, delta=None, delta_color: str = "normal"):
    """Display a metric in a column."""
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def empty_state(message: str):
    """Show an empty state placeholder."""
    st.info(message)


def outcome_color(reward: float | None) -> str:
    if reward is None:
        return "gray"
    return "green" if reward == 1.0 else "red"
