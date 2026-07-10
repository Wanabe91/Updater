from pathlib import Path

from alembic.config import Config


def make_alembic_config(db_path: Path) -> Config:
    alembic_dir = Path(__file__).parent / "alembic"
    config = Config()
    config.set_main_option("script_location", str(alembic_dir))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config