from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str | None = None
    openai_base_url: str = "https://ai.wormsoft.ru/api/gpt"
    openai_model: str = "zai/glm-5.1"
    db_path: Path = Path.home() / ".updater" / "updater.db"
    backup_dir: Path | None = None
    max_depth: int = 10

    model_config = {"env_prefix": "UPDATER_", "env_file": ".env"}


settings = Settings()
