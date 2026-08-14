import logging
from typing import Any, Dict

from src.embeddings import EmbeddingService
from src.vector_store import ChromaVectorStoreService

logger = logging.getLogger(__name__)


class RetrieverService:
    """
    Service responsible for retrieving relevant chunks
    from the vector database for a user query.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: ChromaVectorStoreService,
        top_k: int = 5,
    ):
        if top_k <= 0:
            raise ValueError("top_k value must be greater than 0.")

        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.top_k = top_k

    def retrieve(self, query: str) -> Dict[str, Any]:
        """
        Retrieve top_k relevant chunks for a given query.
        """

        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        logger.info(f"Retrieving relevant chunks for query: {query}")

        query_embedding = self.embedding_service.embed_query(query)

        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=self.top_k,
        )

        logger.info("Retrieval completed successfully")

        return results