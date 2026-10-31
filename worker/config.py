"""Audio worker configuration and private provider credentials."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # worker/.env (optionnel)

BASE_DIR = Path(__file__).resolve().parent

# Local directory for generated and uploaded audio.
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", BASE_DIR / "storage")).resolve()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://renderstudio:renderstudio@127.0.0.1:5433/renderstudio"
)

# Optional secret shared with the web app for internal requests.
WORKER_API_KEY = os.environ.get("WORKER_API_KEY", "")
