"""Application configuration. Secrets come from environment variables (see .env.example)."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv():
    """Tiny .env loader so no extra dependency is needed."""
    env = BASE_DIR / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


_load_dotenv()


class Config:
    # If SECRET_KEY is unset a random one is generated per process (sessions reset on restart).
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    DATABASE = os.environ.get("DATABASE_PATH", str(BASE_DIR / "instance" / "navora.db"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7
    MAX_CONTENT_LENGTH = 256 * 1024
    # Optional external LLM (never required)
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
    LLM_MODEL = os.environ.get("LLM_MODEL", "")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@navora.local")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")  # if empty, seed creates a random one and prints it
    SITE_URL = os.environ.get("SITE_URL", "http://localhost:5000")
    TESTING = False
    RATE_LIMIT_ENABLED = True
