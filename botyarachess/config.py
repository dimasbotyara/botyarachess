"""Application configuration for botyarachess.

Everything that can differ between machines (paths, secret key, ports)
lives here so the rest of the code stays environment-agnostic.
"""
from __future__ import annotations

import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)

HOST = "0.0.0.0"
PORT = 15989

DATABASE_URI = f"sqlite:///{INSTANCE_DIR / 'botyarachess.db'}"

# The secret key is generated once and persisted so sessions survive restarts.
_SECRET_FILE = INSTANCE_DIR / "secret_key"


def _load_secret_key() -> str:
    if _SECRET_FILE.exists():
        key = _SECRET_FILE.read_text(encoding="utf-8").strip()
        if key:
            return key
    key = secrets.token_hex(32)
    _SECRET_FILE.write_text(key, encoding="utf-8")
    return key


class Config:
    SECRET_KEY = _load_secret_key()
    SQLALCHEMY_DATABASE_URI = DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024  # 1 MiB is plenty for a chess app
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 14  # two weeks

    # --- chess engines used by the game review feature ---------------------
    # Checked in this order: explicit env var -> config value -> PATH lookup.
    STOCKFISH_PATH = None  # e.g. "/usr/bin/stockfish"
    GNUCHESS_PATH = None   # e.g. "/usr/bin/gnuchess"

    # --- AI opponent defaults ----------------------------------------------
    AI_MAX_ATTEMPTS = 3        # retries when the model returns an illegal move
    AI_REQUEST_TIMEOUT = 120   # seconds, generous for slow local models
