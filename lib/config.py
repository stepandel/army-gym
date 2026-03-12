import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

JOBS_DIR = Path(os.getenv("JOBS_DIR", "~/Development/pi-agent-simple/jobs")).expanduser()
DB_PATH = Path(os.getenv("DB_PATH", "eval_observatory.db"))
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "pi-agent-swebench")
LANGSMITH_WORKSPACE_ID = os.getenv("LANGSMITH_WORKSPACE_ID")
LANGSMITH_TAGS = ["headless", "harbor-eval"]
