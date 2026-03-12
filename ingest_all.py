"""Unified ingestion: run Harbor ETL then LangSmith ETL."""

import argparse
from pathlib import Path

from lib.config import JOBS_DIR


def main():
    parser = argparse.ArgumentParser(description="Run all ingestion pipelines")
    parser.add_argument("--jobs-dir", type=Path, default=JOBS_DIR)
    parser.add_argument("--force", action="store_true", help="Re-ingest all Harbor jobs")
    parser.add_argument("--skip-langsmith", action="store_true", help="Skip LangSmith ingestion")
    parser.add_argument("--dry-run", action="store_true", help="LangSmith dry run")
    args = parser.parse_args()

    # Phase 1: Harbor
    print("=" * 60)
    print("Phase 1: Harbor ETL")
    print("=" * 60)
    from ingest import ingest_jobs
    from db import init_db, get_connection

    if args.force:
        init_db()
        conn = get_connection()
        conn.execute("DELETE FROM ingest_metadata WHERE key LIKE 'harbor_job:%'")
        conn.commit()
        conn.close()

    ingest_jobs(args.jobs_dir)

    # Phase 2: LangSmith
    if not args.skip_langsmith:
        print()
        print("=" * 60)
        print("Phase 2: LangSmith ETL")
        print("=" * 60)
        from ingest_langsmith import ingest_langsmith
        ingest_langsmith(dry_run=args.dry_run)
    else:
        print("\nSkipping LangSmith ingestion.")

    print("\nAll ingestion complete.")


if __name__ == "__main__":
    main()
