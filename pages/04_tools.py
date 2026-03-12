"""Tool Usage: frequency heatmap, sequence timeline, error rates, last-5-before-failure."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from lib.queries import (
    get_tool_frequency, get_tool_heatmap_data,
    get_last_n_tools_before_failure, get_tool_calls,
    get_tool_success_fail, get_trials,
)
from lib.components import job_selector, empty_state, outcome_filter, apply_outcome_filter

st.title("Tool Usage")

job_id = job_selector()
outcome = outcome_filter()

freq = get_tool_frequency(job_id)
if freq.empty:
    empty_state("No tool call data yet. Run `python ingest_langsmith.py` to fetch traces.")
    st.stop()

# --- Frequency Summary ---
st.subheader("Tool Call Frequency")
tool_summary = freq.groupby("tool_name").agg(
    total_calls=("call_count", "sum"),
    total_errors=("error_count", "sum"),
    avg_duration=("avg_duration_s", "mean"),
).reset_index().sort_values("total_calls", ascending=False)
tool_summary["error_rate"] = tool_summary["total_errors"] / tool_summary["total_calls"]

st.dataframe(
    tool_summary.style.format({
        "avg_duration": "{:.2f}s",
        "error_rate": "{:.1%}",
    }),
    use_container_width=True, hide_index=True,
)

# --- Tool Usage by Trial Outcome ---
st.subheader("Tool Usage by Trial Outcome")
sf = get_tool_success_fail(job_id)
if not sf.empty:
    sf["pass_pct"] = sf["passed_trials"] / sf["trials_using"]
    sf["tests_failed_pct"] = sf["tests_failed_trials"] / sf["trials_using"]
    sf["timeout_pct"] = sf["timeout_trials"] / sf["trials_using"]

    melted = sf.melt(
        id_vars=["tool_name"],
        value_vars=["pass_pct", "tests_failed_pct", "timeout_pct"],
        var_name="outcome", value_name="pct",
    )
    melted["outcome"] = melted["outcome"].map({
        "pass_pct": "Passed", "tests_failed_pct": "Tests Failed", "timeout_pct": "Timeout",
    })
    fig = px.bar(
        melted, x="pct", y="tool_name", color="outcome", orientation="h",
        color_discrete_map={"Passed": "#2ecc71", "Tests Failed": "#e74c3c", "Timeout": "#f39c12"},
        labels={"pct": "% of Trials Using Tool", "tool_name": "Tool"},
    )
    fig.update_layout(
        margin=dict(t=20, b=20), barmode="stack",
        yaxis={"categoryorder": "total ascending"},
        xaxis_tickformat=".0%",
    )
    st.plotly_chart(fig, use_container_width=True)

    display = sf[["tool_name", "trials_using", "passed_trials", "tests_failed_trials", "timeout_trials", "pass_pct"]].copy()
    display.columns = ["Tool", "Trials Using", "Passed", "Tests Failed", "Timeout", "Pass Rate"]
    st.dataframe(
        display.style.format({"Pass Rate": "{:.1%}"}),
        use_container_width=True, hide_index=True,
    )

# --- Heatmap ---
st.subheader("Tool × Task Heatmap")
trials = get_trials(job_id)
filtered_trials = apply_outcome_filter(trials, outcome)
if not filtered_trials.empty:
    filtered_names = set(filtered_trials["trial_name"])
    heatmap = get_tool_heatmap_data(job_id)
    # Filter heatmap to only tasks in filtered trials
    filtered_tasks = set(filtered_trials["task_name"])
    heatmap = heatmap[heatmap["task_name"].isin(filtered_tasks)]
    if not heatmap.empty:
        pivot = heatmap.pivot_table(index="task_name", columns="tool_name", values="call_count", fill_value=0)
        fig = px.imshow(
            pivot, text_auto=True, aspect="auto",
            color_continuous_scale="Blues",
            labels={"color": "Calls"},
        )
        fig.update_layout(margin=dict(t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_state("No heatmap data for this filter.")
else:
    empty_state("No trials for this filter.")

# --- Error Rates by Tool ---
st.subheader("Error Rate by Tool")
fig = px.bar(
    tool_summary[tool_summary["total_errors"] > 0].sort_values("error_rate", ascending=True),
    x="error_rate", y="tool_name", orientation="h",
    labels={"error_rate": "Error Rate", "tool_name": "Tool"},
)
fig.update_layout(margin=dict(t=20, b=20), xaxis_tickformat=".0%")
st.plotly_chart(fig, use_container_width=True)

# --- Last 5 Before Failure ---
if job_id:
    st.subheader("Last 5 Tool Calls Before Failure")
    last5 = get_last_n_tools_before_failure(job_id)
    if not last5.empty:
        # Filter to matching outcome
        if outcome != "All":
            matching_tasks = set(filtered_trials["task_name"])
            last5 = last5[last5["task_name"].isin(matching_tasks)]
        if not last5.empty:
            for task_name in last5["task_name"].unique():
                with st.expander(task_name):
                    subset = last5[last5["task_name"] == task_name][
                        ["call_index", "tool_name", "is_error", "duration_s"]
                    ]
                    st.dataframe(subset, use_container_width=True, hide_index=True)
        else:
            empty_state("No failed trials for this filter.")
    else:
        empty_state("No failed trials without exceptions in this job.")

# --- Tool Sequence Timeline ---
st.subheader("Tool Sequence Timeline")
ls_trials = apply_outcome_filter(trials, outcome)
ls_trials = ls_trials[ls_trials["ls_run_id"].notna()]
if ls_trials.empty:
    empty_state("No LangSmith-linked trials for this filter.")
else:
    trial_name = st.selectbox("Select trial", ls_trials["trial_name"].tolist(), key="tool_timeline_trial")
    if trial_name:
        calls = get_tool_calls(trial_name)
        if not calls.empty and calls["started_at"].notna().any():
            calls = calls.dropna(subset=["started_at", "finished_at"])
            if not calls.empty:
                calls["started_at"] = pd.to_datetime(calls["started_at"])
                calls["finished_at"] = pd.to_datetime(calls["finished_at"])
                fig = px.timeline(
                    calls, x_start="started_at", x_end="finished_at",
                    y="tool_name", color="tool_name",
                    hover_data=["call_index", "is_error"],
                )
                fig.update_layout(margin=dict(t=20, b=20), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                empty_state("No timing data available for tool calls.")
        else:
            empty_state("No timing data available for tool calls.")
