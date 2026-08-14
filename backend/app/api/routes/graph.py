"""API endpoints for Knowledge Graph exploration, entity inspection, and graph visualization."""

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models.graph import Entity, Relationship
from app.services.llm import get_llm_service, LLMService
from app.services.knowledge_graph import KnowledgeGraphService

router = APIRouter(tags=["Knowledge Graph"])


class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    canonical_name: str
    entity_type: str
    description: Optional[str]
    created_at: Any


class RelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    source_entity_id: uuid.UUID
    target_entity_id: uuid.UUID
    relationship_type: str
    confidence: float
    document_id: Optional[uuid.UUID]
    evidence_text: Optional[str]


class GraphVisualizationResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


@router.get(
    "/projects/{project_id}/graph",
    response_model=GraphVisualizationResponse,
    summary="Get project Knowledge Graph visualization data",
)
async def get_project_graph(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve nodes and edges for rendering the project knowledge graph view."""
    e_stmt = select(Entity).where(Entity.project_id == project_id).limit(100)
    e_res = await db.execute(e_stmt)
    entities = e_res.scalars().all()

    r_stmt = select(Relationship).where(Relationship.project_id == project_id).limit(200)
    r_res = await db.execute(r_stmt)
    relationships = r_res.scalars().all()

    nodes = [
        {
            "id": str(e.id),
            "label": e.canonical_name,
            "type": e.entity_type,
            "description": e.description,
        }
        for e in entities
    ]

    edges = [
        {
            "id": str(r.id),
            "source": str(r.source_entity_id),
            "target": str(r.target_entity_id),
            "label": r.relationship_type,
            "confidence": r.confidence,
            "evidence": r.evidence_text,
        }
        for r in relationships
    ]

    return {"nodes": nodes, "edges": edges}


@router.get(
    "/projects/{project_id}/graph/entities",
    response_model=List[EntityResponse],
    summary="List project entities",
)
async def list_entities(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all entities extracted in a project."""
    stmt = select(Entity).where(Entity.project_id == project_id)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get(
    "/projects/{project_id}/graph/query",
    summary="Query Knowledge Graph",
)
async def query_graph(
    project_id: uuid.UUID,
    q: str,
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Query knowledge graph relationships and evidence for specific concepts."""
    kg_service = KnowledgeGraphService(llm_service)
    return await kg_service.query_graph(session=db, project_id=project_id, query=q)
