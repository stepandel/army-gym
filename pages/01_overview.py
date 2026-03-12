"""Job Overview: scorecard, task table, failure category breakdown."""

import streamlit as st
import plotly.express as px
from lib.queries import get_job_summary, get_trials, get_failure_categories
from lib.components import job_selector, metric_card, empty_state

st.title("Job Overview")

job_id = job_selector()

# --- Scorecard ---
summary = get_job_summary()
if summary.empty:
    empty_state("No jobs found. Run `python ingest.py` first.")
    st.stop()

if job_id:
    row = summary[summary["job_id"] == job_id].iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Trials", int(row["trial_count"]))
    with c2:
        metric_card("Pass Rate", f"{row['mean_reward']:.0%}" if row['mean_reward'] is not None else "N/A")
    with c3:
        metric_card("Passed", int(row["passed"]))
    with c4:
        metric_card("Errors", int(row["errors"]))
else:
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Total Jobs", len(summary))
    with c2:
        metric_card("Total Trials", int(summary["trial_count"].sum()))
    with c3:
        avg = summary["mean_reward"].mean()
        metric_card("Avg Pass Rate", f"{avg:.0%}" if avg is not None else "N/A")

# --- Job Summary Table ---
st.subheader("Jobs")
display_cols = ["job_id", "started_at", "trial_count", "passed", "failed", "errors", "mean_reward"]
st.dataframe(
    summary[display_cols].style.format({"mean_reward": "{:.1%}"}, na_rep="—"),
    use_container_width=True,
    hide_index=True,
)

# --- Failure Category Breakdown ---
if job_id:
    st.subheader("Outcome Breakdown")
    cats = get_failure_categories(job_id)
    if not cats.empty:
        fig = px.pie(cats, names="category", values="count", hole=0.4)
        fig.update_layout(margin=dict(t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # --- Trial Table ---
    st.subheader("Trials")
    trials = get_trials(job_id)
    if not trials.empty:
        display = trials[
            ["trial_name", "task_name", "reward", "exception_type",
             "duration_total_s", "tests_passed", "tests_total"]
        ].copy()
        display["reward"] = display["reward"].map({1.0: "Pass", 0.0: "Fail"}).fillna("—")
        st.dataframe(display, use_container_width=True, hide_index=True)
