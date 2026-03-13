"""Time Analysis: duration distributions, phase waterfall, duration-vs-tokens scatter."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from lib.queries import get_duration_stats, get_phase_durations, get_trial_token_summary
from lib.components import job_selector, empty_state, outcome_filter, apply_outcome_filter

OUTCOME_COLORS = {"Passed": "#2ecc71", "Tests Failed": "#e74c3c", "Agent Timeout": "#f39c12", "Verifier Timeout": "#e67e22"}

st.title("Time Analysis")

job_id = job_selector()
outcome = outcome_filter()

durations = apply_outcome_filter(get_duration_stats(job_id), outcome)
if durations.empty:
    empty_state("No duration data available for this filter.")
    st.stop()

# --- Duration Distribution ---
st.subheader("Total Duration Distribution")
fig = px.histogram(
    durations, x="duration_total_s", color="failure_reason",
    nbins=20, barmode="overlay",
    labels={"duration_total_s": "Duration (s)", "failure_reason": "Outcome"},
    color_discrete_map=OUTCOME_COLORS,
)
fig.update_layout(margin=dict(t=20, b=20))
st.plotly_chart(fig, use_container_width=True)

# --- Phase Waterfall ---
if job_id:
    st.subheader("Phase Breakdown by Trial")
    phases = apply_outcome_filter(get_phase_durations(job_id), outcome)
    if not phases.empty:
        phase_cols = ["duration_env_setup_s", "duration_agent_setup_s",
                      "duration_agent_exec_s", "duration_verifier_s"]
        phase_labels = ["Env Setup", "Agent Setup", "Agent Execution", "Verifier"]

        melted = phases.melt(
            id_vars=["task_name", "failure_reason"],
            value_vars=phase_cols,
            var_name="phase", value_name="duration_s",
        )
        melted["phase"] = melted["phase"].map(dict(zip(phase_cols, phase_labels)))
        melted = melted.dropna(subset=["duration_s"])

        fig = px.bar(
            melted, x="duration_s", y="task_name", color="phase",
            orientation="h",
            labels={"duration_s": "Duration (s)", "task_name": "Task"},
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(
            yaxis={"categoryorder": "total ascending"},
            margin=dict(t=20, b=20), barmode="stack",
        )
        st.plotly_chart(fig, use_container_width=True)

# --- Duration vs Tokens Scatter ---
st.subheader("Duration vs Total Tokens")
tokens = apply_outcome_filter(get_trial_token_summary(job_id), outcome)
if tokens.empty:
    empty_state("No LangSmith token data yet. Run `python ingest_langsmith.py` first.")
else:
    merged = durations.merge(tokens[["trial_name", "total_tokens"]], on="trial_name", how="inner")
    if not merged.empty:
        fig = px.scatter(
            merged, x="total_tokens", y="duration_agent_exec_s",
            color="failure_reason", hover_name="task_name",
            labels={"total_tokens": "Total Tokens", "duration_agent_exec_s": "Agent Exec (s)"},
            color_discrete_map=OUTCOME_COLORS,
        )
        fig.update_layout(margin=dict(t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_state("No matched trials with both duration and token data.")
