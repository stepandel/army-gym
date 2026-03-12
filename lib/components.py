"""Shared Streamlit UI components."""

import streamlit as st
import pandas as pd
from lib.queries import get_jobs


def job_selector(key: str = "job_select", allow_all: bool = True) -> str | None:
    """Sidebar job selector. Returns job_id or None for 'All jobs'."""
    jobs = get_jobs()
    if jobs.empty:
        st.sidebar.warning("No jobs ingested yet. Run `python ingest.py` first.")
        return None

    options = ["All jobs"] + jobs["job_id"].tolist() if allow_all else jobs["job_id"].tolist()
    selected = st.sidebar.selectbox("Job", options, key=key)
    if selected == "All jobs":
        return None
    return selected


OUTCOME_OPTIONS = ["All", "Passed", "Tests Failed", "Timeout"]


def outcome_filter(key: str = "outcome_filter") -> str:
    """Sidebar outcome filter. Returns selected outcome or 'All'."""
    return st.sidebar.selectbox("Outcome", OUTCOME_OPTIONS, key=key)


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
    return st.sidebar.selectbox("Trial", options, key=key)


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
