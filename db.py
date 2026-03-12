import sqlite3
from pathlib import Path
from lib.config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    job_dir TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    n_total_trials INTEGER,
    n_completed_trials INTEGER,
    n_errors INTEGER,
    mean_reward REAL,
    source TEXT
);

CREATE TABLE IF NOT EXISTS trials (
    trial_name TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    task_name TEXT NOT NULL,
    source TEXT,
    trial_uri TEXT,
    reward REAL,
    exception_type TEXT,
    exception_message TEXT,
    started_at TEXT,
    finished_at TEXT,
    duration_total_s REAL,
    duration_env_setup_s REAL,
    duration_agent_setup_s REAL,
    duration_agent_exec_s REAL,
    duration_verifier_s REAL,
    agent_output TEXT,
    tests_total INTEGER,
    tests_passed INTEGER,
    tests_failed INTEGER,
    ls_run_id TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

CREATE TABLE IF NOT EXISTS llm_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_name TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    ls_run_id TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_read_tokens INTEGER,
    cache_write_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd REAL,
    started_at TEXT,
    finished_at TEXT,
    duration_s REAL,
    FOREIGN KEY (trial_name) REFERENCES trials(trial_name)
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_name TEXT NOT NULL,
    call_index INTEGER NOT NULL,
    ls_run_id TEXT,
    tool_name TEXT,
    tool_input TEXT,
    tool_output TEXT,
    is_error INTEGER DEFAULT 0,
    started_at TEXT,
    finished_at TEXT,
    duration_s REAL,
    FOREIGN KEY (trial_name) REFERENCES trials(trial_name)
);

CREATE TABLE IF NOT EXISTS ingest_metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_trials_job_id ON trials(job_id);
CREATE INDEX IF NOT EXISTS idx_trials_task_name ON trials(task_name);
CREATE INDEX IF NOT EXISTS idx_llm_turns_trial ON llm_turns(trial_name);
CREATE INDEX IF NOT EXISTS idx_tool_calls_trial ON tool_calls(trial_name);
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path | None = None) -> None:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
