# Agent Eval Observatory

A Streamlit dashboard for analyzing and comparing AI agent evaluation runs. Ingests data from [Harbor](https://github.com/av/harbor) job results and [LangSmith](https://smith.langchain.com/) traces, then provides interactive visualizations of agent performance, token economics, tool usage, and failure patterns.

## Features

- **Overview** -- Scorecard with pass rates, failure categories, and job summary tables
- **Time Analysis** -- Duration distributions, phase waterfall breakdowns (env setup, agent execution, verifier), and duration-vs-token scatter plots
- **Token Economics** -- Token/cost distributions by outcome, cumulative token curves, and cache hit ratio analysis
- **Tool Usage** -- Tool call frequency, error rates, and pass rate per tool
- **Trial Deep Dive** -- Single-trial inspection with verifier test results and turn-by-turn LLM/tool replay
- **Compare Jobs** -- Multi-job pass rate trends, task-by-job result matrices, and regression detection
- **Compare Trials** -- Side-by-side diff of two trials with delta-highlighted metrics

## Setup

### Prerequisites

- Python 3.10+
- A Harbor jobs directory with evaluation results
- LangSmith API key (optional, for LLM trace data)

### Install

```bash
pip install -r requirements.txt
```

### Configure

Copy `.env.example` to `.env` and fill in your values:

```
JOBS_DIR=/path/to/harbor/jobs
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=your-project-name
LANGSMITH_WORKSPACE_ID=your-workspace-id
DB_PATH=eval_observatory.db
```

| Variable | Description |
|---|---|
| `JOBS_DIR` | Path to the directory containing Harbor evaluation job folders |
| `LANGSMITH_API_KEY` | API key from [smith.langchain.com](https://smith.langchain.com/) |
| `LANGSMITH_PROJECT` | LangSmith project name to pull traces from |
| `LANGSMITH_WORKSPACE_ID` | LangSmith workspace ID |
| `DB_PATH` | Path for the SQLite database (default: `eval_observatory.db`) |

## Usage

```bash
# Ingest data and start the dashboard
make serve

# Or run steps separately:
make ingest          # Run both Harbor + LangSmith ETL
streamlit run app.py # Start dashboard at http://localhost:8501
```

You can also run ingestion pipelines independently:

```bash
make ingest-harbor      # Harbor data only
make ingest-langsmith   # LangSmith traces only
```

## Project Structure

```
army-gym/
├── app.py                  # Streamlit entry point
├── db.py                   # SQLite schema and connection management
├── ingest.py               # Harbor ETL pipeline
├── ingest_langsmith.py     # LangSmith ETL pipeline
├── ingest_all.py           # Orchestrates both pipelines
├── lib/
│   ├── config.py           # Environment variable loading
│   ├── components.py       # Shared Streamlit UI widgets
│   └── queries.py          # SQL query functions returning DataFrames
├── pages/
│   ├── 01_overview.py      # Job overview and scorecard
│   ├── 02_time.py          # Timing analysis
│   ├── 03_tokens.py        # Token and cost economics
│   ├── 04_tools.py         # Tool usage patterns
│   ├── 05_deep_dive.py     # Single trial inspection
│   ├── 06_compare.py       # Multi-job comparison
│   └── 07_compare_trials.py# Trial-level diff
├── Makefile
├── requirements.txt
└── .env.example
```

## Architecture

The system has three layers:

1. **Ingestion** -- ETL pipelines parse Harbor job results and fetch matching LangSmith traces. Ingestion is idempotent (re-running skips already-ingested data).
2. **Database** -- SQLite with tables for jobs, trials, LLM turns, tool calls, and ingestion metadata.
3. **Dashboard** -- Multi-page Streamlit app with shared sidebar state for filtering by job and outcome.

LangSmith traces are matched to Harbor trials by comparing instruction text, enabling turn-by-turn analysis of agent LLM calls and tool invocations alongside pass/fail outcomes.
