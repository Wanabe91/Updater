from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Base,
    DependencyRecord,
    DependencyTreeModel,
    Project,
    SuggestionHistory,
    UpdateHistory,
)


class Repository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}")
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        return self._session_factory()

    def get_project(self, project_path: Path) -> Project | None:
        with self.get_session() as session:
            return session.scalar(
                select(Project).where(Project.path == str(project_path.resolve()))
            )

    def get_or_create_project(self, project_path: Path) -> Project:
        resolved = project_path.resolve()
        with self.get_session() as session:
            project = session.scalar(
                select(Project).where(Project.path == str(resolved))
            )
            if project is None:
                project = Project(path=str(resolved), name=resolved.name)
                session.add(project)
                session.commit()
            return project

    def save_dependencies(self, project_id: int, dependencies: list[dict]) -> None:
        with self.get_session() as session:
            session.execute(
                delete(DependencyRecord).where(
                    DependencyRecord.project_id == project_id
                )
            )
            for dep in dependencies:
                session.add(
                    DependencyRecord(
                        project_id=project_id,
                        name=dep["name"],
                        version=dep.get("version", ""),
                        version_specifier=dep.get("version_specifier", ""),
                        is_dev=dep.get("is_dev", False),
                        source_file=dep.get("source", ""),
                        ecosystem=dep.get("ecosystem", ""),
                        latest_version=dep.get("latest_version"),
                        is_outdated=dep.get("is_outdated", False),
                    )
                )
            session.commit()

    def get_dependencies(self, project_id: int) -> list[DependencyRecord]:
        with self.get_session() as session:
            return list(
                session.scalars(
                    select(DependencyRecord)
                    .where(DependencyRecord.project_id == project_id)
                    .order_by(DependencyRecord.ecosystem, DependencyRecord.name)
                )
            )

    def save_update(self, project_id: int, update_data: dict) -> UpdateHistory:
        with self.get_session() as session:
            record = UpdateHistory(
                project_id=project_id,
                package_name=update_data["package_name"],
                old_version=update_data.get("old_version", ""),
                new_version=update_data.get("new_version", ""),
                action=update_data.get("action", "update"),
                success=update_data.get("success", True),
                details=update_data.get("details"),
            )
            session.add(record)
            session.commit()
            return record

    def get_update_history(
        self, project_id: int, limit: int = 20
    ) -> list[UpdateHistory]:
        with self.get_session() as session:
            return list(
                session.scalars(
                    select(UpdateHistory)
                    .where(UpdateHistory.project_id == project_id)
                    .order_by(UpdateHistory.created_at.desc(), UpdateHistory.id.desc())
                    .limit(limit)
                )
            )

    def save_suggestion(
        self, project_id: int, suggestion_data: dict
    ) -> SuggestionHistory:
        with self.get_session() as session:
            record = SuggestionHistory(
                project_id=project_id,
                original_package=suggestion_data["original_package"],
                suggested_package=suggestion_data["suggested_package"],
                reason=suggestion_data.get("reason", ""),
                confidence=suggestion_data.get("confidence", 0.0),
                accepted=suggestion_data.get("accepted"),
            )
            session.add(record)
            session.commit()
            return record

    def save_tree(self, project_id: int, tree_data: dict) -> DependencyTreeModel:
        with self.get_session() as session:
            record = DependencyTreeModel(project_id=project_id, tree_data=tree_data)
            session.add(record)
            session.commit()
            return record

    def get_latest_tree(self, project_id: int) -> DependencyTreeModel | None:
        with self.get_session() as session:
            return session.scalar(
                select(DependencyTreeModel)
                .where(DependencyTreeModel.project_id == project_id)
                .order_by(
                    DependencyTreeModel.created_at.desc(),
                    DependencyTreeModel.id.desc(),
                )
                .limit(1)
            )
