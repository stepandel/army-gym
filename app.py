"""Agent Eval Observatory — Streamlit entry point."""

import streamlit as st

st.set_page_config(
    page_title="Agent Eval Observatory",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

overview = st.Page("pages/01_overview.py", title="Overview", icon="📊", default=True)
time_analysis = st.Page("pages/02_time.py", title="Time Analysis", icon="⏱️")
tokens = st.Page("pages/03_tokens.py", title="Token Economics", icon="🪙")
tools = st.Page("pages/04_tools.py", title="Tool Usage", icon="🔧")
deep_dive = st.Page("pages/05_deep_dive.py", title="Trial Deep Dive", icon="🔍")
compare = st.Page("pages/06_compare.py", title="Compare Jobs", icon="📈")

pg = st.navigation([overview, time_analysis, tokens, tools, deep_dive, compare])
pg.run()
