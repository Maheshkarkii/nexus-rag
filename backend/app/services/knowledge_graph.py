"""Knowledge Graph extraction, resolution, and traversal service."""

import logging
import uuid
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.models.graph import Entity, Relationship
from app.db.models.document_chunk import DocumentChunk
from app.services.llm import LLMService

logger = logging.getLogger("ai_research_assistant.services.knowledge_graph")


class KnowledgeGraphService:
    """Service managing entity and relationship extraction, normalization, resolution, and graph traversal."""

    ENTITY_TYPES = [
        "Person", "Organization", "Paper", "Dataset", "Model",
        "Method", "Algorithm", "Technology", "Concept", "Metric"
    ]

    RELATIONSHIP_TYPES = [
        "authored_by", "published_by", "uses_method", "uses_dataset",
        "evaluated_on", "reports_metric", "contains_concept", "related_to",
        "compares_with", "extends", "improves", "cites"
    ]

    @staticmethod
    def normalize_entity_name(raw_name: str) -> str:
        """Normalize raw entity names by stripping whitespace, corporate suffixes, and unifying casing."""
        if not raw_name:
            return ""
        clean = raw_name.strip()
        # Remove common corporate/entity noise suffixes for canonical matching
        clean = re.sub(r"\b(Inc\.|Corp\.|LLC|Ltd\.|Co\.)\b", "", clean, flags=re.IGNORECASE).strip()
        return clean

    @staticmethod
    def resolve_entity(cname: str, existing_names: List[str]) -> Optional[str]:
        """Resolve entity name against existing canonical names using exact and normalized matching."""
        norm_input = KnowledgeGraphService.normalize_entity_name(cname).lower()
        for name in existing_names:
            norm_existing = KnowledgeGraphService.normalize_entity_name(name).lower()
            if norm_input == norm_existing:
                return name
        return None

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    async def extract_and_store_graph(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        chunks: List[DocumentChunk],
    ) -> Dict[str, int]:
        """Extract entities and relationships from document chunks incrementally."""
        extracted_entities_count = 0
        extracted_rels_count = 0

        for chunk in chunks[:10]: # Limit chunk batching for safe execution
            prompt_text = chunk.content_text[:1500] if hasattr(chunk, "content_text") else str(chunk)[:1500]
            
            system_prompt = (
                "You are an expert NLP Knowledge Graph extraction assistant.\n"
                "Extract structured entities and relationships from the provided research text.\n\n"
                "Allowed Entity Types: " + ", ".join(self.ENTITY_TYPES) + "\n"
                "Allowed Relationship Types: " + ", ".join(self.RELATIONSHIP_TYPES) + "\n\n"
                "Return ONLY a valid JSON object matching this schema:\n"
                "{\n"
                "  \"entities\": [{\"name\": \"...\", \"type\": \"...\", \"description\": \"...\"}],\n"
                "  \"relationships\": [{\"source\": \"...\", \"target\": \"...\", \"type\": \"...\", \"evidence\": \"...\"}]\n"
                "}"
            )
            user_prompt = f"Text:\n{prompt_text}"

            try:
                raw_res = await self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)
                clean_json = re.sub(r"^```json\s*|```\s*$", "", raw_res.strip(), flags=re.MULTILINE)
                graph_data = json.loads(clean_json)

                # Store entities and resolve existing canonicals
                entity_map = {}
                for ent_info in graph_data.get("entities", []):
                    cname = ent_info.get("name", "").strip()
                    etype = ent_info.get("type", "Concept")
                    if not cname:
                        continue

                    # Lookup canonical entity in project
                    stmt = select(Entity).where(
                        Entity.project_id == project_id,
                        Entity.canonical_name == cname,
                    )
                    res = await session.execute(stmt)
                    db_ent = res.scalar_one_or_none()

                    if not db_ent:
                        db_ent = Entity(
                            project_id=project_id,
                            canonical_name=cname,
                            entity_type=etype,
                            description=ent_info.get("description"),
                        )
                        session.add(db_ent)
                        await session.commit()
                        await session.refresh(db_ent)
                        extracted_entities_count += 1

                    entity_map[cname.lower()] = db_ent.id

                # Store relationships
                for rel_info in graph_data.get("relationships", []):
                    src_name = rel_info.get("source", "").strip().lower()
                    tgt_name = rel_info.get("target", "").strip().lower()
                    rtype = rel_info.get("type", "related_to")

                    if src_name in entity_map and tgt_name in entity_map:
                        db_rel = Relationship(
                            project_id=project_id,
                            source_entity_id=entity_map[src_name],
                            target_entity_id=entity_map[tgt_name],
                            relationship_type=rtype,
                            confidence=0.9,
                            document_id=document_id,
                            chunk_id=getattr(chunk, "id", None),
                            evidence_text=rel_info.get("evidence", "")[:900],
                        )
                        session.add(db_rel)
                        extracted_rels_count += 1

                await session.commit()

            except Exception as e:
                logger.warning(f"Knowledge graph extraction skipped for chunk: {e}")

        return {"entities": extracted_entities_count, "relationships": extracted_rels_count}

    async def query_graph(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        query: str,
        max_depth: int = 2,
    ) -> List[Dict[str, Any]]:
        """Query knowledge graph for entities and connected relationships matching a search query."""
        stmt = select(Entity).where(Entity.project_id == project_id)
        res = await session.execute(stmt)
        all_entities = res.scalars().all()

        matched_entities = [
            e for e in all_entities
            if query.lower() in e.canonical_name.lower() or (e.description and query.lower() in e.description.lower())
        ]

        if not matched_entities:
            return []

        matched_ids = [e.id for e in matched_entities]

        rel_stmt = select(Relationship).where(
            Relationship.project_id == project_id,
            (Relationship.source_entity_id.in_(matched_ids)) | (Relationship.target_entity_id.in_(matched_ids)),
        ).limit(50)
        rel_res = await session.execute(rel_stmt)
        relationships = rel_res.scalars().all()

        results = []
        for r in relationships:
            results.append({
                "relationship_id": str(r.id),
                "source_entity_id": str(r.source_entity_id),
                "target_entity_id": str(r.target_entity_id),
                "relationship_type": r.relationship_type,
                "confidence": r.confidence,
                "document_id": str(r.document_id) if r.document_id else None,
                "evidence": r.evidence_text,
            })

        return results

    async def remove_document_graph(self, session: AsyncSession, document_id: uuid.UUID) -> None:
        """Remove graph relationships belonging exclusively to a deleted document."""
        stmt = delete(Relationship).where(Relationship.document_id == document_id)
        await session.execute(stmt)
        await session.commit()
