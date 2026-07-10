from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base, Project, DependencyRecord, UpdateHistory, SuggestionHistory, DependencyTreeModel


class Repository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")
        self._session_factory = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        return self._session_factory()

    def get_or_create_project(self, project_path: Path) -> Project:
        raise NotImplementedError

    def save_dependencies(self, project_id: int, dependencies: list[dict]) -> None:
        raise NotImplementedError

    def get_dependencies(self, project_id: int) -> list[DependencyRecord]:
        raise NotImplementedError

    def save_update(self, project_id: int, update_data: dict) -> UpdateHistory:
        raise NotImplementedError

    def get_update_history(self, project_id: int, limit: int = 20) -> list[UpdateHistory]:
        raise NotImplementedError

    def save_suggestion(self, project_id: int, suggestion_data: dict) -> SuggestionHistory:
        raise NotImplementedError

    def save_tree(self, project_id: int, tree_data: dict) -> DependencyTreeModel:
        raise NotImplementedError

    def get_latest_tree(self, project_id: int) -> Optional[DependencyTreeModel]:
        raise NotImplementedError