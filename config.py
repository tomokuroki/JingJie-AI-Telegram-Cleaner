from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv, set_key

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
ENV_EXAMPLE_PATH = BASE_DIR / ".env.example"


def ensure_env() -> None:
    if not ENV_PATH.exists() and ENV_EXAMPLE_PATH.exists():
        shutil.copy2(ENV_EXAMPLE_PATH, ENV_PATH)


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _csv_set(name: str) -> set[str]:
    return {item.strip().lower() for item in os.getenv(name, "").split(",") if item.strip()}


@dataclass(slots=True)
class Settings:
    lang: str
    telegram_api_id: int | None
    telegram_api_hash: str
    telegram_phone: str
    session_name: str
    ollama_base_url: str
    ollama_model: str
    ollama_timeout: int
    adult_threshold: float
    spam_threshold: float
    junk_threshold: float
    recent_messages: int
    max_text_chars: int
    scan_broadcast_channels: bool
    scan_megagroups: bool
    dry_run: bool
    protect_admins: bool
    protect_verified: bool
    safe_usernames: set[str]
    safe_ids: set[int]


def load_settings() -> Settings:
    ensure_env()
    load_dotenv(ENV_PATH, override=True)

    api_id_raw = os.getenv("TELEGRAM_API_ID", "").strip()
    api_id = int(api_id_raw) if api_id_raw.isdigit() else None

    safe_ids: set[int] = set()
    for item in _csv_set("SAFE_IDS"):
        try:
            safe_ids.add(int(item))
        except ValueError:
            pass

    lang = os.getenv("APP_LANG", "zh").strip().lower()
    if lang not in {"zh", "en", "ru"}:
        lang = "zh"

    return Settings(
        lang=lang,
        telegram_api_id=api_id,
        telegram_api_hash=os.getenv("TELEGRAM_API_HASH", "").strip(),
        telegram_phone=os.getenv("TELEGRAM_PHONE", "").strip(),
        session_name=os.getenv("SESSION_NAME", "jingjie_account").strip() or "jingjie_account",
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:8b").strip() or "qwen3:8b",
        ollama_timeout=max(10, _int("OLLAMA_TIMEOUT", 120)),
        adult_threshold=min(1.0, max(0.0, _float("ADULT_THRESHOLD", 0.72))),
        spam_threshold=min(1.0, max(0.0, _float("SPAM_THRESHOLD", 0.82))),
        junk_threshold=min(1.0, max(0.0, _float("JUNK_THRESHOLD", 0.90))),
        recent_messages=max(1, min(50, _int("RECENT_MESSAGES", 12))),
        max_text_chars=max(1000, min(30000, _int("MAX_TEXT_CHARS", 9000))),
        scan_broadcast_channels=_bool("SCAN_BROADCAST_CHANNELS", True),
        scan_megagroups=_bool("SCAN_MEGAGROUPS", False),
        dry_run=_bool("DRY_RUN", True),
        protect_admins=_bool("PROTECT_ADMINS", True),
        protect_verified=_bool("PROTECT_VERIFIED", False),
        safe_usernames=_csv_set("SAFE_USERNAMES"),
        safe_ids=safe_ids,
    )


def save_env_value(key: str, value: str) -> None:
    ensure_env()
    set_key(str(ENV_PATH), key, value, quote_mode="never")
    os.environ[key] = value
