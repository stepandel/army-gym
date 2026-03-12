"""Job Overview: scorecard, task table, failure category breakdown."""

import streamlit as st
import plotly.express as px
from lib.queries import get_job_summary, get_trials, get_failure_categories
from lib.components import job_selector, metric_card, empty_state, outcome_filter, apply_outcome_filter

st.title("Job Overview")

job_id = job_selector()
outcome = outcome_filter()

# --- Scorecard ---
summary = get_job_summary()
if summary.empty:
    empty_state("No jobs found. Run `python ingest.py` first.")
    st.stop()

if job_id:
    row = summary[summary["job_id"] == job_id].iloc[0]
    cats = get_failure_categories(job_id)
    cat_counts = dict(zip(cats["category"], cats["count"])) if not cats.empty else {}
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Trials", int(row["trial_count"]))
    with c2:
        metric_card("Pass Rate", f"{row['mean_reward']:.0%}" if row['mean_reward'] is not None else "N/A")
    with c3:
        metric_card("Passed", int(cat_counts.get("Passed", 0)))
    with c4:
        metric_card("Tests Failed", int(cat_counts.get("Tests Failed", 0)))
    with c5:
        metric_card("Timed Out", int(cat_counts.get("Timeout", 0)))
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
        color_map = {
            "Passed": "#2ecc71",
            "Tests Failed": "#e74c3c",
            "Timeout": "#f39c12",
        }
        fig = px.pie(
            cats, names="category", values="count", hole=0.4,
            color="category", color_discrete_map=color_map,
        )
        fig.update_layout(margin=dict(t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # --- Trial Table ---
    st.subheader("Trials")
    trials = apply_outcome_filter(get_trials(job_id), outcome)
    if not trials.empty:
        display = trials[
            ["trial_name", "task_name", "failure_reason",
             "duration_agent_exec_s", "tests_passed", "tests_total"]
        ].copy()
        display.columns = ["Trial", "Task", "Outcome", "Agent Exec (s)", "Tests Passed", "Tests Total"]
        st.dataframe(display, use_container_width=True, hide_index=True)
