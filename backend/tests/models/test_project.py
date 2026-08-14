"""Unit tests for Project model CRUD, UUID primary key, and timezone-aware timestamps."""

from datetime import datetime
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import pytest
from app.db.models.project import Project


@pytest.mark.asyncio
async def test_project_create_and_read(db_session: AsyncSession) -> None:
    """Verify creating a project assigns a valid UUID and timestamps."""
    project = Project(
        name="Attention & RAG Synthesis",
        description="Comprehensive review of Retrieval-Augmented Generation architectures.",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    assert project.id is not None
    assert isinstance(project.id, uuid.UUID)
    assert project.name == "Attention & RAG Synthesis"
    assert project.description == "Comprehensive review of Retrieval-Augmented Generation architectures."
    assert isinstance(project.created_at, datetime)
    assert isinstance(project.updated_at, datetime)
    assert project.created_at.tzinfo is not None

    # Query from database
    stmt = select(Project).where(Project.id == project.id)
    result = await db_session.execute(stmt)
    fetched = result.scalar_one_or_none()

    assert fetched is not None
    assert fetched.name == "Attention & RAG Synthesis"


@pytest.mark.asyncio
async def test_project_update(db_session: AsyncSession) -> None:
    """Verify updating a project's name and description."""
    project = Project(name="Initial Name", description="Initial Description")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    # Perform update
    project.name = "Updated Research Workspace"
    project.description = "Updated Workspace Description"
    await db_session.commit()
    await db_session.refresh(project)

    assert project.name == "Updated Research Workspace"
    assert project.description == "Updated Workspace Description"


@pytest.mark.asyncio
async def test_project_delete(db_session: AsyncSession) -> None:
    """Verify deleting a project removes it from the database."""
    project = Project(name="Temporary Scratch Workspace")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    project_id = project.id

    # Delete project
    await db_session.delete(project)
    await db_session.commit()

    # Query again
    stmt = select(Project).where(Project.id == project_id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None
