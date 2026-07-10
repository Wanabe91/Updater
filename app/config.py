from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    db_path: Path = Path.home() / ".updater" / "updater.db"
    backup_dir: Optional[Path] = None
    max_depth: int = 10

    model_config = {"env_prefix": "UPDATER_", "env_file": ".env"}


settings = Settings()