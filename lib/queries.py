"""SQL query functions returning DataFrames."""

import pandas as pd
from db import get_connection


def _query(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


# --- Job Overview ---


def get_jobs() -> pd.DataFrame:
    return _query(
        """SELECT job_id, started_at, finished_at, n_total_trials,
                  n_completed_trials, n_errors, mean_reward, source
           FROM jobs ORDER BY job_id DESC"""
    )


def get_trials(job_id: str | None = None) -> pd.DataFrame:
    if job_id:
        return _query(
            f"""SELECT *, {FAILURE_REASON_CASE} as failure_reason
                FROM trials WHERE job_id = ? ORDER BY task_name""",
            (job_id,),
        )
    return _query(
        f"""SELECT *, {FAILURE_REASON_CASE} as failure_reason
            FROM trials ORDER BY job_id DESC, task_name"""
    )


def get_job_summary() -> pd.DataFrame:
    return _query(
        """SELECT j.job_id, j.started_at, j.mean_reward, j.source,
                  COUNT(t.trial_name) as trial_count,
                  SUM(CASE WHEN t.reward = 1.0 THEN 1 ELSE 0 END) as passed,
                  SUM(CASE WHEN t.reward = 0.0 THEN 1 ELSE 0 END) as failed,
                  SUM(CASE WHEN t.exception_type IS NOT NULL THEN 1 ELSE 0 END) as errors
           FROM jobs j
           LEFT JOIN trials t ON j.job_id = t.job_id
           GROUP BY j.job_id
           ORDER BY j.job_id DESC"""
    )


FAILURE_REASON_CASE = """
    CASE
      WHEN reward = 1.0 THEN 'Passed'
      WHEN exception_type IS NOT NULL THEN 'Exception: ' || exception_type
      WHEN reward = 0.0 AND duration_agent_exec_s >= 590 THEN 'Timeout'
      WHEN reward = 0.0 THEN 'Tests Failed'
      ELSE 'Other'
    END
"""


def get_failure_categories(job_id: str) -> pd.DataFrame:
    return _query(
        f"""SELECT {FAILURE_REASON_CASE} as category,
             COUNT(*) as count
           FROM trials WHERE job_id = ?
           GROUP BY category ORDER BY count DESC""",
        (job_id,),
    )


# --- Time Analysis ---


def get_duration_stats(job_id: str | None = None) -> pd.DataFrame:
    where = "WHERE t.job_id = ?" if job_id else ""
    params = (job_id,) if job_id else ()
    return _query(
        f"""SELECT t.trial_name, t.task_name, t.reward, t.exception_type,
                   t.duration_total_s, t.duration_env_setup_s,
                   t.duration_agent_setup_s, t.duration_agent_exec_s,
                   t.duration_verifier_s,
                   {FAILURE_REASON_CASE} as failure_reason
            FROM trials t {where}
            ORDER BY t.duration_total_s DESC""",
        params,
    )


def get_phase_durations(job_id: str) -> pd.DataFrame:
    return _query(
        f"""SELECT task_name, reward,
                  duration_env_setup_s, duration_agent_setup_s,
                  duration_agent_exec_s, duration_verifier_s,
                  {FAILURE_REASON_CASE} as failure_reason
           FROM trials WHERE job_id = ? AND duration_total_s IS NOT NULL
           ORDER BY duration_total_s DESC""",
        (job_id,),
    )


# --- Token Analysis ---


def get_trial_token_summary(job_id: str | None = None) -> pd.DataFrame:
    where = "WHERE t.job_id = ?" if job_id else ""
    params = (job_id,) if job_id else ()
    return _query(
        f"""SELECT t.trial_name, t.task_name, t.reward,
                   {FAILURE_REASON_CASE} as failure_reason,
                   COUNT(l.id) as n_turns,
                   SUM(l.input_tokens) as total_input,
                   SUM(l.output_tokens) as total_output,
                   SUM(l.cache_read_tokens) as total_cache_read,
                   SUM(l.cache_write_tokens) as total_cache_write,
                   SUM(l.total_tokens) as total_tokens,
                   SUM(l.cost_usd) as total_cost
            FROM trials t
            JOIN llm_turns l ON t.trial_name = l.trial_name
            {where}
            GROUP BY t.trial_name
            ORDER BY total_tokens DESC""",
        params,
    )


def get_llm_turns(trial_name: str) -> pd.DataFrame:
    return _query(
        """SELECT * FROM llm_turns WHERE trial_name = ? ORDER BY turn_index""",
        (trial_name,),
    )


def get_cumulative_tokens(trial_name: str) -> pd.DataFrame:
    return _query(
        """SELECT turn_index, total_tokens, input_tokens, output_tokens,
                  cache_read_tokens, cost_usd
           FROM llm_turns WHERE trial_name = ?
           ORDER BY turn_index""",
        (trial_name,),
    )


# --- Tool Analysis ---


def get_tool_frequency(job_id: str | None = None) -> pd.DataFrame:
    where = "WHERE t.job_id = ?" if job_id else ""
    params = (job_id,) if job_id else ()
    return _query(
        f"""SELECT tc.tool_name, COUNT(*) as call_count,
                   SUM(tc.is_error) as error_count,
                   AVG(tc.duration_s) as avg_duration_s,
                   t.reward
            FROM tool_calls tc
            JOIN trials t ON tc.trial_name = t.trial_name
            {where}
            GROUP BY tc.tool_name, t.reward
            ORDER BY call_count DESC""",
        params,
    )


def get_tool_success_fail(job_id: str | None = None) -> pd.DataFrame:
    where = "WHERE t.job_id = ?" if job_id else ""
    params = (job_id,) if job_id else ()
    return _query(
        f"""SELECT tc.tool_name,
                   COUNT(DISTINCT tc.trial_name) as trials_using,
                   COUNT(DISTINCT CASE WHEN t.reward = 1.0 THEN tc.trial_name END) as passed_trials,
                   COUNT(DISTINCT CASE WHEN t.reward = 0.0 AND t.duration_agent_exec_s < 590 THEN tc.trial_name END) as tests_failed_trials,
                   COUNT(DISTINCT CASE WHEN t.reward = 0.0 AND t.duration_agent_exec_s >= 590 THEN tc.trial_name END) as timeout_trials
            FROM tool_calls tc
            JOIN trials t ON tc.trial_name = t.trial_name
            {where}
            GROUP BY tc.tool_name
            ORDER BY trials_using DESC""",
        params,
    )


def get_tool_calls(trial_name: str) -> pd.DataFrame:
    return _query(
        """SELECT * FROM tool_calls WHERE trial_name = ? ORDER BY call_index""",
        (trial_name,),
    )


def get_last_n_tools_before_failure(job_id: str, n: int = 5) -> pd.DataFrame:
    return _query(
        """SELECT tc.trial_name, t.task_name, tc.tool_name, tc.is_error,
                  tc.call_index, tc.duration_s
           FROM tool_calls tc
           JOIN trials t ON tc.trial_name = t.trial_name
           WHERE t.job_id = ? AND t.reward = 0.0 AND t.exception_type IS NULL
             AND tc.call_index >= (
               SELECT MAX(tc2.call_index) - ? + 1
               FROM tool_calls tc2 WHERE tc2.trial_name = tc.trial_name
             )
           ORDER BY tc.trial_name, tc.call_index""",
        (job_id, n),
    )


# --- Tool Heatmap ---


def get_tool_heatmap_data(job_id: str | None = None) -> pd.DataFrame:
    where = "WHERE t.job_id = ?" if job_id else ""
    params = (job_id,) if job_id else ()
    return _query(
        f"""SELECT t.task_name, tc.tool_name, COUNT(*) as call_count
            FROM tool_calls tc
            JOIN trials t ON tc.trial_name = t.trial_name
            {where}
            GROUP BY t.task_name, tc.tool_name""",
        params,
    )


# --- Deep Dive ---


def get_trial_detail(trial_name: str) -> pd.DataFrame:
    return _query("SELECT * FROM trials WHERE trial_name = ?", (trial_name,))


def get_trial_timeline(trial_name: str) -> pd.DataFrame:
    """Interleaved LLM turns and tool calls for turn-by-turn replay."""
    return _query(
        """SELECT 'llm' as type, turn_index as idx, model, input_tokens, output_tokens,
                  cache_read_tokens, total_tokens, cost_usd,
                  started_at, finished_at, duration_s,
                  NULL as tool_name, NULL as tool_input, NULL as tool_output, NULL as is_error
           FROM llm_turns WHERE trial_name = ?
           UNION ALL
           SELECT 'tool' as type, call_index as idx, NULL, NULL, NULL,
                  NULL, NULL, NULL,
                  started_at, finished_at, duration_s,
                  tool_name, tool_input, tool_output, is_error
           FROM tool_calls WHERE trial_name = ?
           ORDER BY started_at, idx""",
        (trial_name, trial_name),
    )


# --- Comparative ---


def get_task_across_jobs() -> pd.DataFrame:
    return _query(
        f"""SELECT t.task_name, t.job_id, t.reward, t.exception_type,
                  t.duration_agent_exec_s,
                  {FAILURE_REASON_CASE} as failure_reason
           FROM trials t
           ORDER BY t.task_name, t.job_id"""
    )


def get_regressions() -> pd.DataFrame:
    """Tasks that passed in an earlier job but failed in a later job."""
    return _query(
        """SELECT a.task_name,
                  a.job_id as passed_job, a.reward as passed_reward,
                  b.job_id as failed_job, b.reward as failed_reward
           FROM trials a
           JOIN trials b ON a.task_name = b.task_name AND a.job_id < b.job_id
           WHERE a.reward = 1.0 AND b.reward = 0.0
           ORDER BY b.job_id DESC, a.task_name"""
    )


def get_exception_trends() -> pd.DataFrame:
    return _query(
        """SELECT job_id, exception_type, COUNT(*) as count
           FROM trials
           WHERE exception_type IS NOT NULL
           GROUP BY job_id, exception_type
           ORDER BY job_id"""
    )
