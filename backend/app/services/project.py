"""Service and repository operations for Research Projects."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


async def create_project(session: AsyncSession, payload: ProjectCreate) -> Project:
    """Create and persist a new research project workspace."""
    project = Project(
        name=payload.name,
        description=payload.description,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def get_projects(session: AsyncSession) -> Sequence[Project]:
    """Retrieve all research projects ordered by created_at descending."""
    stmt = select(Project).order_by(Project.created_at.desc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_project_by_id(session: AsyncSession, project_id: uuid.UUID) -> Project | None:
    """Retrieve a single research project by its UUID primary key."""
    stmt = select(Project).where(Project.id == project_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_project(
    session: AsyncSession, project: Project, payload: ProjectUpdate
) -> Project:
    """Apply partial updates to an existing research project."""
    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description

    project.updated_at = datetime.now(UTC)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(session: AsyncSession, project: Project) -> None:
    """Remove a research project workspace from the database."""
    await session.delete(project)
    await session.commit()
