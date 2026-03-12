"""Compare Jobs: pass rate trends, regression detector, exception trends."""

import streamlit as st
import plotly.express as px
import pandas as pd
from lib.queries import get_job_summary, get_task_across_jobs, get_regressions, get_exception_trends
from lib.components import empty_state

st.title("Compare Jobs")

summary = get_job_summary()
if summary.empty or len(summary) < 2:
    empty_state("Need at least 2 jobs to compare. Run more evals first.")
    st.stop()

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
if not task_jobs.empty:
    pivot = task_jobs.pivot_table(
        index="task_name", columns="job_id", values="reward", aggfunc="first"
    )
    # Color: 1.0 green, 0.0 red, NaN gray
    styled = pivot.style.applymap(
        lambda v: "background-color: #2ecc71; color: white" if v == 1.0
        else "background-color: #e74c3c; color: white" if v == 0.0
        else "background-color: #ecf0f1",
        subset=pivot.columns,
    ).format("{:.0f}", na_rep="—")
    st.dataframe(styled, use_container_width=True)

# --- Regressions ---
st.subheader("Regressions")
regressions = get_regressions()
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
if exc.empty:
    st.success("No exceptions across jobs.")
else:
    fig = px.bar(
        exc, x="job_id", y="count", color="exception_type",
        labels={"count": "Count", "job_id": "Job", "exception_type": "Exception"},
    )
    fig.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)
