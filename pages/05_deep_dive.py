"""Trial Deep Dive: metadata, turn-by-turn replay, verifier results, timeline."""

import json
import streamlit as st
import plotly.express as px
import pandas as pd
from pathlib import Path
from lib.queries import get_trials, get_trial_detail, get_trial_timeline, get_llm_turns, get_tool_calls
from lib.components import job_selector, empty_state

st.title("Trial Deep Dive")

job_id = job_selector()
trials = get_trials(job_id)

if trials.empty:
    empty_state("No trials found.")
    st.stop()

trial_name = st.sidebar.selectbox("Trial", trials["trial_name"].tolist())
if not trial_name:
    st.stop()

detail = get_trial_detail(trial_name)
if detail.empty:
    empty_state("Trial not found.")
    st.stop()

t = detail.iloc[0]

# --- Metadata ---
st.subheader("Trial Metadata")
c1, c2, c3, c4 = st.columns(4)
with c1:
    reward = t["reward"]
    st.metric("Outcome", "Pass" if reward == 1.0 else "Fail" if reward == 0.0 else "Error")
with c2:
    st.metric("Duration", f"{t['duration_total_s']:.1f}s" if t["duration_total_s"] else "—")
with c3:
    st.metric("Tests", f"{int(t['tests_passed'] or 0)}/{int(t['tests_total'] or 0)}")
with c4:
    st.metric("Exception", t["exception_type"] or "None")

# Phase timing bar
phases = {
    "Env Setup": t["duration_env_setup_s"],
    "Agent Setup": t["duration_agent_setup_s"],
    "Agent Execution": t["duration_agent_exec_s"],
    "Verifier": t["duration_verifier_s"],
}
phase_df = pd.DataFrame([
    {"Phase": k, "Duration (s)": v} for k, v in phases.items() if v is not None
])
if not phase_df.empty:
    fig = px.bar(
        phase_df, x="Duration (s)", y="Phase", orientation="h",
        color="Phase", color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(margin=dict(t=10, b=10), showlegend=False, height=200)
    st.plotly_chart(fig, use_container_width=True)

# --- Agent Output ---
if t["agent_output"]:
    with st.expander("Agent Output", expanded=False):
        st.markdown(t["agent_output"])

# --- Verifier (CTRF) Results ---
trial_uri = t["trial_uri"]
if trial_uri:
    ctrf_path = Path(trial_uri.replace("file://", "")) / "verifier" / "ctrf.json"
    if ctrf_path.exists():
        with open(ctrf_path) as f:
            ctrf = json.load(f)
        tests = ctrf.get("results", {}).get("tests", [])
        if tests:
            with st.expander("Verifier Test Results", expanded=True):
                for test in tests:
                    status = test.get("status", "unknown")
                    icon = "✅" if status == "passed" else "❌"
                    dur = test.get("duration", 0)
                    st.markdown(f"{icon} **{test['name']}** — {dur*1000:.1f}ms")

# --- Turn-by-Turn Replay ---
st.subheader("Turn-by-Turn Replay")
timeline = get_trial_timeline(trial_name)

if timeline.empty:
    empty_state("No LangSmith trace data for this trial. Run `python ingest_langsmith.py`.")
else:
    for i, row in timeline.iterrows():
        if row["type"] == "llm":
            label = f"LLM Turn {int(row['idx'])} — {row['model'] or 'unknown'}"
            tokens_str = f"in:{row['input_tokens'] or 0:,.0f} out:{row['output_tokens'] or 0:,.0f}"
            if row["cache_read_tokens"]:
                tokens_str += f" cache:{row['cache_read_tokens']:,.0f}"
            cost = f"${row['cost_usd']:.4f}" if row["cost_usd"] else ""

            with st.expander(f"🧠 {label} | {tokens_str} {cost}", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Input Tokens", f"{row['input_tokens'] or 0:,.0f}")
                with col2:
                    st.metric("Output Tokens", f"{row['output_tokens'] or 0:,.0f}")
                with col3:
                    st.metric("Duration", f"{row['duration_s']:.1f}s" if row["duration_s"] else "—")

        elif row["type"] == "tool":
            err = "❌ " if row["is_error"] else ""
            tool_label = f"{err}🔧 {row['tool_name']} (#{int(row['idx'])})"
            dur = f" — {row['duration_s']:.1f}s" if row["duration_s"] else ""

            with st.expander(f"{tool_label}{dur}", expanded=False):
                if row["tool_input"]:
                    st.markdown("**Input:**")
                    try:
                        inp = json.loads(row["tool_input"])
                        st.json(inp)
                    except (json.JSONDecodeError, TypeError):
                        st.code(str(row["tool_input"])[:2000])
                if row["tool_output"]:
                    st.markdown("**Output:**")
                    st.code(str(row["tool_output"])[:2000])
