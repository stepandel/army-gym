"""Compare Jobs: pass rate trends, regression detector, exception trends."""

import streamlit as st
import plotly.express as px
import pandas as pd
from lib.queries import get_job_summary, get_task_across_jobs, get_regressions, get_exception_trends
from lib.components import empty_state, outcome_filter, apply_outcome_filter, job_multiselect

OUTCOME_COLORS = {"Passed": "#2ecc71", "Tests Failed": "#e74c3c", "Agent Timeout": "#f39c12", "Verifier Timeout": "#e67e22"}

st.title("Compare Jobs")

outcome = outcome_filter()

summary = get_job_summary()
if summary.empty or len(summary) < 2:
    empty_state("Need at least 2 jobs to compare. Run more evals first.")
    st.stop()

selected_jobs = job_multiselect()

if len(selected_jobs) < 2:
    empty_state("Select at least 2 jobs to compare.")
    st.stop()

summary = summary[summary["job_id"].isin(selected_jobs)]

# --- Pass Rate Trend ---
st.subheader("Pass Rate Across Jobs")
fig = px.line(
    summary.sort_values("job_id"),
    x="job_id", y="mean_reward", markers=True,
    labels={"mean_reward": "Pass Rate", "job_id": "Job"},
)
fig.update_layout(margin=dict(t=20, b=20), yaxis_tickformat=".0%")
st.plotly_chart(fig, use_container_width=True)

# --- Task × Job Matrix ---
st.subheader("Task Results Across Jobs")
task_jobs = get_task_across_jobs()
task_jobs = task_jobs[task_jobs["job_id"].isin(selected_jobs)]
task_jobs = apply_outcome_filter(task_jobs, outcome)
if not task_jobs.empty:
    pivot = task_jobs.pivot_table(
        index="task_name", columns="job_id", values="failure_reason", aggfunc="first"
    )

    def color_outcome(v):
        if v == "Passed":
            return "background-color: #2ecc71; color: white"
        elif v == "Tests Failed":
            return "background-color: #e74c3c; color: white"
        elif v == "Agent Timeout":
            return "background-color: #f39c12; color: white"
        elif v == "Verifier Timeout":
            return "background-color: #e67e22; color: white"
        return "background-color: #ecf0f1"

    styled = pivot.style.map(color_outcome, subset=pivot.columns)
    st.dataframe(styled, use_container_width=True)
else:
    empty_state("No trials for this filter.")

# --- Regressions ---
st.subheader("Regressions")
regressions = get_regressions()
regressions = regressions[
    regressions["passed_job"].isin(selected_jobs) & regressions["failed_job"].isin(selected_jobs)
]
if regressions.empty:
    st.success("No regressions detected.")
else:
    st.warning(f"{len(regressions)} regression(s) found")
    st.dataframe(
        regressions[["task_name", "passed_job", "failed_job"]],
        use_container_width=True, hide_index=True,
    )

# --- Exception Trends ---
st.subheader("Exception Trends")
exc = get_exception_trends()
exc = exc[exc["job_id"].isin(selected_jobs)]
if exc.empty:
    st.success("No exceptions across selected jobs.")
else:
    fig = px.bar(
        exc, x="job_id", y="count", color="exception_type",
        labels={"count": "Count", "job_id": "Job", "exception_type": "Exception"},
    )
    fig.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)
