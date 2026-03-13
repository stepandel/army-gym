"""Harbor ETL: walk jobs/, parse result.json + verifier files, upsert into SQLite."""

import argparse
import base64
import json
import sys
from datetime import datetime
from pathlib import Path

from db import get_connection, init_db
from lib.config import JOBS_DIR


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    ts = ts.rstrip("Z")
    return datetime.fromisoformat(ts)


def phase_duration_s(phase: dict | None) -> float | None:
    if not phase:
        return None
    start = parse_iso(phase.get("started_at"))
    end = parse_iso(phase.get("finished_at"))
    if start and end:
        return (end - start).total_seconds()
    return None


def ingest_jobs(jobs_dir: Path) -> None:
    init_db()
    conn = get_connection()

    # Find already-ingested jobs
    ingested = {
        row["key"]
        for row in conn.execute(
            "SELECT key FROM ingest_metadata WHERE key LIKE 'harbor_job:%'"
        ).fetchall()
    }

    job_dirs = sorted(
        d for d in jobs_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    )

    total_trials = 0
    total_jobs = 0

    for job_dir in job_dirs:
        job_id = job_dir.name
        meta_key = f"harbor_job:{job_id}"

        if meta_key in ingested:
            continue

        job_result_path = job_dir / "result.json"
        if not job_result_path.exists():
            continue

        with open(job_result_path) as f:
            job_result = json.load(f)

        # Determine source from stats
        source = None
        stats = job_result.get("stats", {}).get("evals", {})
        for eval_key in stats:
            if "terminal-bench" in eval_key:
                source = "terminal-bench"
            elif "swebench" in eval_key:
                source = "swebench"
            break

        # Only ingest terminal-bench for now
        if source != "terminal-bench":
            continue

        eval_stats = next(iter(stats.values()), {})

        conn.execute(
            """INSERT OR REPLACE INTO jobs
               (job_id, job_dir, started_at, finished_at, n_total_trials,
                n_completed_trials, n_errors, mean_reward, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                str(job_dir),
                job_result.get("started_at"),
                job_result.get("finished_at"),
                job_result.get("n_total_trials"),
                eval_stats.get("n_trials"),
                eval_stats.get("n_errors"),
                (eval_stats.get("metrics") or [{}])[0].get("mean"),
                source,
            ),
        )

        # Walk trial directories
        trial_dirs = sorted(
            d
            for d in job_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

        job_trial_count = 0
        for trial_dir in trial_dirs:
            result_path = trial_dir / "result.json"
            if not result_path.exists():
                continue

            with open(result_path) as f:
                trial = json.load(f)

            # Skip non-terminal-bench
            if "terminal-bench" not in (trial.get("source") or ""):
                continue

            # Parse verifier results
            reward = None
            vr = trial.get("verifier_result")
            if vr and vr.get("rewards"):
                reward = vr["rewards"].get("reward")

            # Parse exception info
            exc = trial.get("exception_info")
            exception_type = exc.get("exception_type") if exc else None
            exception_message = exc.get("exception_message") if exc else None

            # Parse timing
            total_start = parse_iso(trial.get("started_at"))
            total_end = parse_iso(trial.get("finished_at"))
            duration_total = (
                (total_end - total_start).total_seconds()
                if total_start and total_end
                else None
            )

            # Agent output
            agent_output = None
            ar = trial.get("agent_result")
            if ar and ar.get("metadata"):
                agent_output = ar["metadata"].get("agent_output")

            # Extract instruction from agent command
            instruction = None
            cmd_file = trial_dir / "agent" / "command-0" / "command.txt"
            if cmd_file.exists():
                cmd_text = cmd_file.read_text()
                if "base64:" in cmd_text:
                    b64_part = cmd_text.split("base64:")[-1].strip().strip('"').strip("'")
                    try:
                        instruction = base64.b64decode(b64_part + "==").decode("utf-8", errors="replace")
                    except Exception:
                        pass

            # CTRF verifier data
            tests_total = tests_passed = tests_failed = None
            ctrf_path = trial_dir / "verifier" / "ctrf.json"
            if ctrf_path.exists():
                with open(ctrf_path) as f:
                    ctrf = json.load(f)
                summary = ctrf.get("results", {}).get("summary", {})
                tests_total = summary.get("tests")
                tests_passed = summary.get("passed")
                tests_failed = summary.get("failed")

            conn.execute(
                """INSERT OR REPLACE INTO trials
                   (trial_name, job_id, task_name, source, trial_uri,
                    reward, exception_type, exception_message,
                    started_at, finished_at,
                    duration_total_s, duration_env_setup_s, duration_agent_setup_s,
                    duration_agent_exec_s, duration_verifier_s,
                    agent_output, instruction, tests_total, tests_passed, tests_failed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trial["trial_name"],
                    job_id,
                    trial["task_name"],
                    trial.get("source"),
                    trial.get("trial_uri"),
                    reward,
                    exception_type,
                    exception_message,
                    trial.get("started_at"),
                    trial.get("finished_at"),
                    duration_total,
                    phase_duration_s(trial.get("environment_setup")),
                    phase_duration_s(trial.get("agent_setup")),
                    phase_duration_s(trial.get("agent_execution")),
                    phase_duration_s(trial.get("verifier")),
                    agent_output,
                    instruction,
                    tests_total,
                    tests_passed,
                    tests_failed,
                ),
            )
            job_trial_count += 1

        # Mark job as ingested
        conn.execute(
            "INSERT OR REPLACE INTO ingest_metadata (key, value) VALUES (?, ?)",
            (meta_key, str(job_trial_count)),
        )
        total_trials += job_trial_count
        total_jobs += 1
        print(f"  Ingested job {job_id}: {job_trial_count} terminal-bench trials")

    conn.commit()
    conn.close()
    print(f"\nDone: {total_jobs} new jobs, {total_trials} new trials ingested.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Harbor eval jobs into SQLite")
    parser.add_argument(
        "--jobs-dir",
        type=Path,
        default=JOBS_DIR,
        help="Path to Harbor jobs directory",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest all jobs (ignore ingest_metadata)",
    )
    args = parser.parse_args()

    if args.force:
        init_db()
        conn = get_connection()
        conn.execute("DELETE FROM ingest_metadata WHERE key LIKE 'harbor_job:%'")
        conn.commit()
        conn.close()

    print(f"Ingesting from {args.jobs_dir}")
    ingest_jobs(args.jobs_dir)
