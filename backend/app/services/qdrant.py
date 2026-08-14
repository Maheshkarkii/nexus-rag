import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import get_settings

logger = logging.getLogger("ai_research_assistant.services.qdrant")


class QdrantService:
    """Dedicated service managing connection and operations on the Qdrant vector database."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str | None = None,
        timeout: int | None = None,
    ) -> None:
        settings = get_settings()
        self.url = url or settings.QDRANT_URL
        self.api_key = api_key or settings.QDRANT_API_KEY
        self.collection_name = collection_name or settings.QDRANT_COLLECTION_NAME
        self.timeout = timeout or settings.QDRANT_TIMEOUT
        self._client: QdrantClient | None = None

    def connect(self) -> QdrantClient:
        """Initialize the Qdrant HTTP client (cached)."""
        if self._client is not None:
            return self._client

        logger.info(f"Connecting to Qdrant server at: {self.url} (timeout={self.timeout})")
        # For local development, api_key can be empty
        self._client = QdrantClient(
            url=self.url,
            api_key=self.api_key or None,
            timeout=self.timeout,
        )
        return self._client

    def collection_exists(self) -> bool:
        """Check if the configured collection exists."""
        client = self.connect()
        try:
            return client.collection_exists(self.collection_name)
        except Exception as exc:
            logger.error(f"Error checking collection existence in Qdrant: {exc}")
            raise RuntimeError(f"Could not connect to Qdrant: {exc}") from exc

    def ensure_collection(self, dimension: int, distance_metric: str = "Cosine") -> None:
        """Ensure Qdrant collection exists and is compatible with dimension and metric."""
        client = self.connect()
        
        # 1. Choose Distance metric
        metric = qmodels.Distance.COSINE
        if distance_metric.lower() == "dot":
            metric = qmodels.Distance.DOT
        elif distance_metric.lower() == "euclid":
            metric = qmodels.Distance.EUCLID

        # 2. Check if collection exists
        if not self.collection_exists():
            logger.info(f"Creating Qdrant collection '{self.collection_name}' (dim={dimension}, metric={distance_metric})...")
            try:
                client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=dimension,
                        distance=metric,
                    ),
                )
            except Exception as exc:
                logger.error(f"Failed to create collection '{self.collection_name}': {exc}")
                raise RuntimeError(f"Failed to create Qdrant collection: {exc}") from exc
        else:
            # 3. Collection exists: verify compatibility
            logger.info(f"Qdrant collection '{self.collection_name}' exists. Verifying compatibility...")
            try:
                col_info = client.get_collection(self.collection_name)
                actual_size = col_info.config.params.vectors.size
                actual_distance = col_info.config.params.vectors.distance

                if actual_size != dimension:
                    raise ValueError(
                        f"Incompatible vector dimension in collection '{self.collection_name}'. "
                        f"Expected {dimension}, found {actual_size}."
                    )
                if actual_distance != metric:
                    raise ValueError(
                        f"Incompatible distance metric in collection '{self.collection_name}'. "
                        f"Expected {metric}, found {actual_distance}."
                    )
                logger.info("Collection compatibility check passed.")
            except ValueError:
                raise
            except Exception as exc:
                logger.error(f"Failed to retrieve Qdrant collection configuration: {exc}")
                raise RuntimeError(f"Failed to verify Qdrant collection: {exc}") from exc

    def upsert_points(self, points: list[Any]) -> None:
        """Upsert a batch of points into Qdrant."""
        client = self.connect()
        try:
            client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
        except Exception as exc:
            logger.error(f"Qdrant upsert failed: {exc}")
            raise RuntimeError(f"Vector upsert failed: {exc}") from exc

    def delete_points(self, points_selector: Any) -> None:
        """Delete specific points from Qdrant matching selector filter."""
        client = self.connect()
        try:
            client.delete(
                collection_name=self.collection_name,
                points_selector=points_selector,
                wait=True,
            )
        except Exception as exc:
            logger.error(f"Qdrant point deletion failed: {exc}")
            raise RuntimeError(f"Vector deletion failed: {exc}") from exc

    def health_check(self) -> bool:
        """Verify connection to Qdrant cluster by fetching collections list."""
        try:
            client = self.connect()
            client.get_collections()
            return True
        except Exception as exc:
            logger.warning(f"Qdrant health check probe failed: {exc}")
            return False


# Singleton Qdrant service instance
default_qdrant_service = QdrantService()


def get_qdrant_service() -> QdrantService:
    """FastAPI dependency for QdrantService."""
    return default_qdrant_service
