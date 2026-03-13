"""Compare Trials: side-by-side diff of two trials."""

import json
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from pathlib import Path
from lib.queries import (
    get_trials, get_trial_detail, get_trial_token_totals,
    get_trial_tool_summary, get_cumulative_tokens,
)
from lib.components import empty_state

st.title("Compare Trials")

all_trials = get_trials()
if all_trials.empty:
    empty_state("No trials found.")
    st.stop()

# Build labels: task_name (job_id) - outcome
all_trials["label"] = all_trials["task_name"] + " (" + all_trials["job_id"] + ")"
trial_options = all_trials["trial_name"].tolist()
trial_labels = dict(zip(all_trials["trial_name"], all_trials["label"]))

# --- Selectors ---
col_a, col_b = st.columns(2)
with col_a:
    trial_a = st.selectbox("Trial A", trial_options, format_func=lambda x: trial_labels[x], key="cmp_a")
with col_b:
    default_b = min(1, len(trial_options) - 1)
    trial_b = st.selectbox("Trial B", trial_options, index=default_b, format_func=lambda x: trial_labels[x], key="cmp_b")

if trial_a == trial_b:
    st.warning("Select two different trials to compare.")
    st.stop()

# --- Load data ---
da = get_trial_detail(trial_a).iloc[0]
db = get_trial_detail(trial_b).iloc[0]
tok_a = get_trial_token_totals(trial_a).iloc[0]
tok_b = get_trial_token_totals(trial_b).iloc[0]
tools_a = get_trial_tool_summary(trial_a)
tools_b = get_trial_tool_summary(trial_b)


def delta_str(val_a, val_b, fmt=".1f", suffix="", invert=False):
    """Format a delta between two values."""
    if val_a is None or val_b is None or pd.isna(val_a) or pd.isna(val_b):
        return None
    diff = val_b - val_a
    if diff == 0:
        return None
    return f"{diff:+{fmt}}{suffix}"


# --- Outcome ---
st.subheader("Outcome")
col_a, col_b = st.columns(2)
with col_a:
    reason = da["failure_reason"]
    color = {"Passed": "green", "Tests Failed": "red", "Timeout": "orange"}.get(reason, "gray")
    st.markdown(f"**Trial A**: :{color}[{reason}]")
with col_b:
    reason = db["failure_reason"]
    color = {"Passed": "green", "Tests Failed": "red", "Timeout": "orange"}.get(reason, "gray")
    st.markdown(f"**Trial B**: :{color}[{reason}]")

# --- Metrics side-by-side ---
st.subheader("Metrics")

metrics = [
    ("Agent Exec", "duration_agent_exec_s", da, db, ".1f", "s"),
    ("Total Duration", "duration_total_s", da, db, ".1f", "s"),
    ("Env Setup", "duration_env_setup_s", da, db, ".1f", "s"),
    ("Agent Setup", "duration_agent_setup_s", da, db, ".1f", "s"),
    ("Verifier", "duration_verifier_s", da, db, ".1f", "s"),
]

col_a, col_b = st.columns(2)
for label, key, a, b, fmt, suffix in metrics:
    va = a[key]
    vb = b[key]
    display_a = f"{va:{fmt}}{suffix}" if va is not None and not pd.isna(va) else "—"
    display_b = f"{vb:{fmt}}{suffix}" if vb is not None and not pd.isna(vb) else "—"
    with col_a:
        st.metric(label, display_a)
    with col_b:
        st.metric(label, display_b, delta=delta_str(va, vb, fmt, suffix), delta_color="inverse")

# --- Tests ---
st.subheader("Verifier Tests")
col_a, col_b = st.columns(2)
with col_a:
    p, t = da["tests_passed"], da["tests_total"]
    st.metric("Tests", f"{int(p or 0)}/{int(t or 0)}" if t else "—")
with col_b:
    p, t = db["tests_passed"], db["tests_total"]
    st.metric("Tests", f"{int(p or 0)}/{int(t or 0)}" if t else "—")

# Show individual test diffs from ctrf.json
ctrf_results = {}
for label, trial in [("A", da), ("B", db)]:
    uri = trial["trial_uri"]
    if uri:
        ctrf_path = Path(uri.replace("file://", "")) / "verifier" / "ctrf.json"
        if ctrf_path.exists():
            with open(ctrf_path) as f:
                ctrf = json.load(f)
            ctrf_results[label] = {
                t["name"]: t["status"] for t in ctrf.get("results", {}).get("tests", [])
            }

if ctrf_results.get("A") and ctrf_results.get("B"):
    all_tests = sorted(set(ctrf_results["A"]) | set(ctrf_results["B"]))
    rows = []
    for test in all_tests:
        sa = ctrf_results["A"].get(test, "—")
        sb = ctrf_results["B"].get(test, "—")
        changed = sa != sb
        rows.append({"Test": test, "Trial A": sa, "Trial B": sb, "Changed": changed})
    test_df = pd.DataFrame(rows)
    changed = test_df[test_df["Changed"]]
    if not changed.empty:
        st.markdown("**Changed tests:**")
        st.dataframe(changed[["Test", "Trial A", "Trial B"]], use_container_width=True, hide_index=True)
    else:
        st.success("All test results identical.")
    with st.expander("All tests"):
        st.dataframe(test_df[["Test", "Trial A", "Trial B"]], use_container_width=True, hide_index=True)

# --- Tokens ---
st.subheader("Tokens")
token_metrics = [
    ("LLM Turns", "n_turns", ",.0f", ""),
    ("Total Tokens", "total_tokens", ",.0f", ""),
    ("Input Tokens", "total_input", ",.0f", ""),
    ("Output Tokens", "total_output", ",.0f", ""),
    ("Cache Read", "total_cache_read", ",.0f", ""),
    ("Cost", "total_cost", ".4f", "$"),
]

col_a, col_b = st.columns(2)
for label, key, fmt, prefix in token_metrics:
    va = tok_a[key]
    vb = tok_b[key]
    display_a = f"{prefix}{va:{fmt}}" if va is not None and not pd.isna(va) else "—"
    display_b = f"{prefix}{vb:{fmt}}" if vb is not None and not pd.isna(vb) else "—"
    with col_a:
        st.metric(label, display_a)
    with col_b:
        d = delta_str(va, vb, fmt, "")
        st.metric(label, display_b, delta=d, delta_color="inverse")

# --- Cumulative token curves ---
cum_a = get_cumulative_tokens(trial_a)
cum_b = get_cumulative_tokens(trial_b)
if not cum_a.empty or not cum_b.empty:
    st.subheader("Cumulative Tokens")
    fig = go.Figure()
    if not cum_a.empty:
        cum_a["cumulative"] = cum_a["total_tokens"].cumsum()
        fig.add_trace(go.Scatter(
            x=cum_a["turn_index"], y=cum_a["cumulative"],
            mode="lines+markers", name=f"A: {da['task_name']}",
            line=dict(color="#3498db"),
        ))
    if not cum_b.empty:
        cum_b["cumulative"] = cum_b["total_tokens"].cumsum()
        fig.add_trace(go.Scatter(
            x=cum_b["turn_index"], y=cum_b["cumulative"],
            mode="lines+markers", name=f"B: {db['task_name']}",
            line=dict(color="#e67e22"),
        ))
    fig.update_layout(
        xaxis_title="Turn Index", yaxis_title="Cumulative Tokens",
        margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Tool usage comparison ---
st.subheader("Tool Usage")
if not tools_a.empty or not tools_b.empty:
    all_tools = sorted(set(tools_a["tool_name"].tolist() if not tools_a.empty else []) |
                       set(tools_b["tool_name"].tolist() if not tools_b.empty else []))
    ta = dict(zip(tools_a["tool_name"], tools_a["calls"])) if not tools_a.empty else {}
    tb = dict(zip(tools_b["tool_name"], tools_b["calls"])) if not tools_b.empty else {}
    ea = dict(zip(tools_a["tool_name"], tools_a["errors"])) if not tools_a.empty else {}
    eb = dict(zip(tools_b["tool_name"], tools_b["errors"])) if not tools_b.empty else {}

    rows = []
    for tool in all_tools:
        ca, cb = int(ta.get(tool, 0)), int(tb.get(tool, 0))
        era, erb = int(ea.get(tool, 0)), int(eb.get(tool, 0))
        rows.append({
            "Tool": tool,
            "A Calls": ca, "B Calls": cb, "Diff": cb - ca,
            "A Errors": era, "B Errors": erb,
        })
    tool_df = pd.DataFrame(rows).sort_values("A Calls", ascending=False)
    st.dataframe(tool_df, use_container_width=True, hide_index=True)

    # Bar chart
    chart_df = pd.DataFrame({
        "Tool": all_tools * 2,
        "Calls": [ta.get(t, 0) for t in all_tools] + [tb.get(t, 0) for t in all_tools],
        "Trial": ["A"] * len(all_tools) + ["B"] * len(all_tools),
    })
    import plotly.express as px
    fig = px.bar(
        chart_df, x="Calls", y="Tool", color="Trial", orientation="h",
        barmode="group",
        color_discrete_map={"A": "#3498db", "B": "#e67e22"},
    )
    fig.update_layout(margin=dict(t=20, b=20), yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)
else:
    empty_state("No tool data available for these trials.")
