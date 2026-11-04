"""App settings. Override any value with an environment variable (e.g. PORT=9000)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "SyncFlow Campus Engine"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = _bool("DEBUG", True)

    # Optional: enables the Gemini fallback in the timetable parser.
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Demo speed: how many real seconds one "kitchen minute" takes.
    # 60 = real time. Set SIM_SECONDS_PER_MINUTE=5 for a fast stage demo.
    sim_seconds_per_minute: float = float(os.getenv("SIM_SECONDS_PER_MINUTE", "60"))
    tick_interval_seconds: float = 1.0

    # Timetable gap defaults (minutes).
    default_walk_buffer: int = 7
    default_break_minutes: int = 30

    seed_file: Path = field(default=BASE_DIR / "data" / "seed_campus.json")
    frontend_dir: Path = field(default=PROJECT_ROOT / "frontend")


settings = Settings()
