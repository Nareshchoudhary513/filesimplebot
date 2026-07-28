"""
config.py

Loads and validates all configuration for FileStoreBot from environment
variables. Keeping configuration in one place makes the rest of the
codebase easy to reason about and keeps secrets out of source control.
"""

from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _parse_int(name: str, default: int = 0) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        raise RuntimeError(f"Environment variable {name} must be an integer, got: {value!r}")


def _parse_int_list(name: str) -> List[int]:
    raw = os.getenv(name, "")
    ids: List[int] = []
    for chunk in raw.replace(" ", "").split(","):
        if not chunk:
            continue
        try:
            ids.append(int(chunk))
        except ValueError:
            raise RuntimeError(f"Environment variable {name} contains a non-integer value: {chunk!r}")
    return ids


# ---- Telegram API credentials ----
API_ID: int = _parse_int("API_ID")
API_HASH: str = _require("API_HASH")
BOT_TOKEN: str = _require("BOT_TOKEN")

# ---- MongoDB ----
MONGO_URI: str = _require("MONGO_URI")
DATABASE_NAME: str = os.getenv("DATABASE_NAME", "filestorebot")

# ---- Force Subscribe ----
# Channel username (e.g. "mychannel") or numeric id (e.g. -1001234567890).
# Leave empty to disable force-subscribe entirely.
FORCE_SUB_CHANNEL: str = os.getenv("FORCE_SUB_CHANNEL", "").strip()

# ---- Admins ----
ADMINS: List[int] = _parse_int_list("ADMINS")

# ---- URL Shortener (optional) ----
SHORTENER_API_KEY: str = os.getenv("SHORTENER_API_KEY", "").strip()
SHORTENER_BASE_URL: str = os.getenv("SHORTENER_BASE_URL", "").strip()

# ---- Misc ----
SESSION_NAME: str = os.getenv("SESSION_NAME", "FileStoreBot")


def is_admin(user_id: int) -> bool:
    """Return True if the given Telegram user id is a configured admin."""
    return user_id in ADMINS


def validate() -> None:
    """Fail fast with a clear message if mandatory config is missing."""
    if not API_ID or not API_HASH or not BOT_TOKEN:
        raise RuntimeError("API_ID, API_HASH, and BOT_TOKEN must all be set.")
    if not MONGO_URI:
        raise RuntimeError("MONGO_URI must be set.")
    if not ADMINS:
        raise RuntimeError(
            "ADMINS must contain at least one Telegram user id, "
            "otherwise nobody will be able to generate links."
        )
