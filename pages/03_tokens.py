"""Token Economics: distributions, cumulative curves, cost breakdown, cache analysis."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from lib.queries import get_trial_token_summary, get_cumulative_tokens
from lib.components import job_selector, empty_state, outcome_filter, apply_outcome_filter

OUTCOME_COLORS = {"Passed": "#2ecc71", "Tests Failed": "#e74c3c", "Agent Timeout": "#f39c12", "Verifier Timeout": "#e67e22"}

st.title("Token Economics")

job_id = job_selector()
outcome = outcome_filter()

tokens = apply_outcome_filter(get_trial_token_summary(job_id), outcome)
if tokens.empty:
    empty_state("No LangSmith token data for this filter. Run `python ingest_langsmith.py` to fetch traces.")
    st.stop()

# --- Scorecard ---
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Trials with Data", len(tokens))
with c2:
    st.metric("Total Tokens", f"{tokens['total_tokens'].sum():,.0f}")
with c3:
    st.metric("Total Cost", f"${tokens['total_cost'].sum():.2f}")
with c4:
    cache_ratio = tokens["total_cache_read"].sum() / max(
        tokens["total_input"].sum() + tokens["total_cache_read"].sum(), 1
    )
    st.metric("Cache Hit Ratio", f"{cache_ratio:.0%}")

# --- Token Distribution ---
st.subheader("Token Distribution by Outcome")
fig = px.box(
    tokens, x="failure_reason", y="total_tokens", color="failure_reason",
    points="all", hover_name="task_name",
    color_discrete_map=OUTCOME_COLORS,
    labels={"total_tokens": "Total Tokens", "failure_reason": "Outcome"},
)
fig.update_layout(margin=dict(t=20, b=20))
st.plotly_chart(fig, use_container_width=True)

# --- Cost Breakdown ---
st.subheader("Cost by Trial")
fig = px.bar(
    tokens.sort_values("total_cost", ascending=True),
    x="total_cost", y="task_name", color="failure_reason", orientation="h",
    labels={"total_cost": "Cost (USD)", "task_name": "Task"},
    color_discrete_map=OUTCOME_COLORS,
)
fig.update_layout(margin=dict(t=20, b=20), yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig, use_container_width=True)

# --- Cumulative Token Curve ---
st.subheader("Cumulative Token Curve")
trial_name = st.selectbox(
    "Select trial", tokens["trial_name"].tolist(), key="token_curve_trial"
)
if trial_name:
    cum = get_cumulative_tokens(trial_name)
    if not cum.empty:
        cum["cumulative_tokens"] = cum["total_tokens"].cumsum()
        cum["cumulative_cost"] = cum["cost_usd"].cumsum()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=cum["turn_index"], y=cum["cumulative_tokens"],
            mode="lines+markers", name="Cumulative Tokens",
        ))
        fig.update_layout(
            xaxis_title="Turn Index", yaxis_title="Cumulative Tokens",
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

# --- Cache Analysis ---
st.subheader("Cache Hit Ratio by Trial")
tokens["cache_ratio"] = tokens["total_cache_read"] / (
    tokens["total_input"] + tokens["total_cache_read"]
).replace(0, 1)
fig = px.bar(
    tokens.sort_values("cache_ratio"), x="cache_ratio", y="task_name",
    orientation="h", color="failure_reason",
    labels={"cache_ratio": "Cache Hit Ratio", "task_name": "Task"},
    color_discrete_map=OUTCOME_COLORS,
)
fig.update_layout(margin=dict(t=20, b=20), yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig, use_container_width=True)
