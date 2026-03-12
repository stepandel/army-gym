"""LangSmith ETL: fetch traces, match to Harbor trials, populate llm_turns + tool_calls."""

import argparse
import json
import time
from datetime import datetime, timedelta, timezone

from langsmith import Client

from db import get_connection, init_db
from lib.config import LANGSMITH_PROJECT, LANGSMITH_TAGS, LANGSMITH_WORKSPACE_ID


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    if isinstance(ts, datetime):
        return ts
    ts = ts.rstrip("Z")
    return datetime.fromisoformat(ts)


def run_duration_s(run) -> float | None:
    if run.start_time and run.end_time:
        return (run.end_time - run.start_time).total_seconds()
    return None


def extract_usage(run) -> dict:
    """Extract token usage from run.extra.metadata.usage or run.total_tokens etc."""
    usage = {}
    # Try extra.metadata.usage first (pi-agent style)
    meta = (run.extra or {}).get("metadata", {})
    u = meta.get("usage", {})
    if u:
        usage["input_tokens"] = u.get("input") or u.get("input_tokens")
        usage["output_tokens"] = u.get("output") or u.get("output_tokens")
        usage["cache_read_tokens"] = u.get("cacheRead") or u.get("cache_read_input_tokens")
        usage["cache_write_tokens"] = u.get("cacheWrite") or u.get("cache_creation_input_tokens")
        usage["total_tokens"] = u.get("totalTokens") or u.get("total_tokens")
        cost = u.get("cost")
        if isinstance(cost, dict):
            usage["cost_usd"] = cost.get("total")
        else:
            usage["cost_usd"] = cost
        return usage

    # Fallback to run-level token counts
    if hasattr(run, "total_tokens") and run.total_tokens:
        usage["total_tokens"] = run.total_tokens
    if hasattr(run, "prompt_tokens") and run.prompt_tokens:
        usage["input_tokens"] = run.prompt_tokens
    if hasattr(run, "completion_tokens") and run.completion_tokens:
        usage["output_tokens"] = run.completion_tokens
    return usage


def match_trial(run, trials_by_task: dict, trials_by_name: dict) -> str | None:
    """Match a LangSmith root run to a Harbor trial."""
    inputs = run.inputs or {}

    # Try matching by instruction text to task content
    instruction = inputs.get("instruction", "")
    session_id = inputs.get("sessionId", "")

    # Try direct task name match from instruction or session metadata
    for task_name, trial_rows in trials_by_task.items():
        for trial in trial_rows:
            # Time overlap: run must overlap with agent_execution phase
            trial_start = parse_iso(trial["started_at"])
            trial_end = parse_iso(trial["finished_at"])
            if not trial_start or not trial_end:
                continue

            run_start = run.start_time
            run_end = run.end_time
            if not run_start or not run_end:
                continue

            # Make all timezone-aware for comparison
            if trial_start.tzinfo is None:
                trial_start = trial_start.replace(tzinfo=timezone.utc)
            if trial_end.tzinfo is None:
                trial_end = trial_end.replace(tzinfo=timezone.utc)
            if run_start.tzinfo is None:
                run_start = run_start.replace(tzinfo=timezone.utc)
            if run_end.tzinfo is None:
                run_end = run_end.replace(tzinfo=timezone.utc)

            # Check time overlap with some buffer
            buffer = timedelta(minutes=2)
            if run_start <= trial_end + buffer and run_end >= trial_start - buffer:
                return trial["trial_name"]

    return None


def ingest_langsmith(dry_run: bool = False) -> None:
    init_db()
    conn = get_connection()
    client_kwargs = {}
    if LANGSMITH_WORKSPACE_ID:
        client_kwargs["workspace_id"] = LANGSMITH_WORKSPACE_ID
    client = Client(**client_kwargs)

    # Load trials needing LangSmith data
    unlinked = conn.execute(
        "SELECT trial_name, task_name, started_at, finished_at FROM trials WHERE ls_run_id IS NULL"
    ).fetchall()
    if not unlinked:
        print("All trials already have LangSmith links.")
        return

    # Build lookup structures
    trials_by_task: dict[str, list] = {}
    for row in unlinked:
        trials_by_task.setdefault(row["task_name"], []).append(dict(row))
    trials_by_name = {row["trial_name"]: dict(row) for row in unlinked}

    # Get time window from trials
    all_starts = [parse_iso(r["started_at"]) for r in unlinked if r["started_at"]]
    all_ends = [parse_iso(r["finished_at"]) for r in unlinked if r["finished_at"]]
    if not all_starts or not all_ends:
        print("No timing data to match against.")
        return

    window_start = min(all_starts) - timedelta(hours=1)
    window_end = max(all_ends) + timedelta(hours=1)
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=timezone.utc)
    if window_end.tzinfo is None:
        window_end = window_end.replace(tzinfo=timezone.utc)

    print(f"Fetching LangSmith runs from {window_start} to {window_end}")
    print(f"Looking for {len(unlinked)} unlinked trials")

    # Check already-ingested runs
    ingested_runs = {
        row["key"].split(":", 1)[1]
        for row in conn.execute(
            "SELECT key FROM ingest_metadata WHERE key LIKE 'ls_run:%'"
        ).fetchall()
    }

    # Fetch root runs
    runs = list(client.list_runs(
        project_name=LANGSMITH_PROJECT,
        filter=f'and(eq(is_root, true), has(tags, "headless"), has(tags, "harbor-eval"))',
        start_time=window_start,
        end_time=window_end,
    ))
    print(f"Found {len(runs)} root runs in LangSmith")

    matched = 0
    for run in runs:
        run_id = str(run.id)
        if run_id in ingested_runs:
            continue

        trial_name = match_trial(run, trials_by_task, trials_by_name)
        if not trial_name:
            continue

        matched += 1
        print(f"  Matched: {trial_name} -> {run_id}")

        if dry_run:
            continue

        # Update trial with LangSmith run ID
        conn.execute(
            "UPDATE trials SET ls_run_id = ? WHERE trial_name = ?",
            (run_id, trial_name),
        )

        # Fetch child runs
        time.sleep(0.5)  # Rate limiting
        child_runs = list(client.list_runs(
            project_name=LANGSMITH_PROJECT,
            filter=f'eq(parent_run_id, "{run_id}")',
        ))

        # Also fetch deeper descendants for tool calls nested under LLM runs
        all_children = list(child_runs)
        for child in child_runs:
            if child.child_run_ids:
                time.sleep(0.3)
                grandchildren = list(client.list_runs(
                    project_name=LANGSMITH_PROJECT,
                    filter=f'eq(parent_run_id, "{child.id}")',
                ))
                all_children.extend(grandchildren)

        # Separate LLM turns and tool calls
        llm_idx = 0
        tool_idx = 0

        for child in sorted(all_children, key=lambda r: r.start_time or datetime.min):
            if child.run_type == "llm":
                usage = extract_usage(child)
                conn.execute(
                    """INSERT INTO llm_turns
                       (trial_name, turn_index, ls_run_id, model,
                        input_tokens, output_tokens, cache_read_tokens,
                        cache_write_tokens, total_tokens, cost_usd,
                        started_at, finished_at, duration_s)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        trial_name, llm_idx, str(child.id),
                        (child.extra or {}).get("metadata", {}).get("model") or (child.extra or {}).get("metadata", {}).get("ls_model_name"),
                        usage.get("input_tokens"),
                        usage.get("output_tokens"),
                        usage.get("cache_read_tokens"),
                        usage.get("cache_write_tokens"),
                        usage.get("total_tokens"),
                        usage.get("cost_usd"),
                        child.start_time.isoformat() if child.start_time else None,
                        child.end_time.isoformat() if child.end_time else None,
                        run_duration_s(child),
                    ),
                )
                llm_idx += 1

            elif child.run_type == "tool":
                tool_input = None
                if child.inputs:
                    try:
                        tool_input = json.dumps(child.inputs, default=str)[:5000]
                    except (TypeError, ValueError):
                        tool_input = str(child.inputs)[:5000]

                tool_output = None
                if child.outputs:
                    try:
                        tool_output = json.dumps(child.outputs, default=str)[:5000]
                    except (TypeError, ValueError):
                        tool_output = str(child.outputs)[:5000]

                conn.execute(
                    """INSERT INTO tool_calls
                       (trial_name, call_index, ls_run_id, tool_name,
                        tool_input, tool_output, is_error,
                        started_at, finished_at, duration_s)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        trial_name, tool_idx, str(child.id),
                        child.name,
                        tool_input,
                        tool_output,
                        1 if child.error else 0,
                        child.start_time.isoformat() if child.start_time else None,
                        child.end_time.isoformat() if child.end_time else None,
                        run_duration_s(child),
                    ),
                )
                tool_idx += 1

        # Mark run as ingested
        conn.execute(
            "INSERT OR REPLACE INTO ingest_metadata (key, value) VALUES (?, ?)",
            (f"ls_run:{run_id}", trial_name),
        )

        # Remove from unlinked lookup to prevent double-matching
        task = trials_by_name.get(trial_name, {}).get("task_name")
        if task and task in trials_by_task:
            trials_by_task[task] = [
                t for t in trials_by_task[task] if t["trial_name"] != trial_name
            ]

        print(f"    -> {llm_idx} LLM turns, {tool_idx} tool calls")

    conn.commit()
    conn.close()
    print(f"\nDone: {matched} trials matched to LangSmith traces.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest LangSmith traces")
    parser.add_argument("--dry-run", action="store_true", help="Match only, don't write")
    args = parser.parse_args()
    ingest_langsmith(dry_run=args.dry_run)
