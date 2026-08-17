from unittest.mock import MagicMock, patch

import pytest
from qdrant_client.http import models as qmodels

from app.services.qdrant import QdrantService


@pytest.fixture(autouse=True)
def reset_qdrant_service_state():
    """Reset shared clients dict before each test."""
    QdrantService._shared_clients.clear()
    yield
    QdrantService._shared_clients.clear()


@patch("app.services.qdrant.QdrantClient")
def test_qdrant_service_connection(mock_client_class: MagicMock) -> None:
    service = QdrantService(url="http://mock-qdrant:6333", api_key="test-key", timeout=30)
    client = service.connect()
    
    mock_client_class.assert_called_once_with(
        url="http://mock-qdrant:6333",
        api_key="test-key",
        timeout=30,
    )
    assert client is not None


@patch("app.services.qdrant.QdrantClient")
def test_ensure_collection_creates_when_missing(mock_client_class: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.collection_exists.return_value = False

    service = QdrantService(url="http://mock-qdrant:6333", collection_name="test_collection")
    service.ensure_collection(dimension=384, distance_metric="Cosine")

    mock_client.collection_exists.assert_called_once_with("test_collection")
    mock_client.create_collection.assert_called_once()


@patch("app.services.qdrant.QdrantClient")
def test_ensure_collection_checks_compatibility(mock_client_class: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.collection_exists.return_value = True

    # Setup matching config info
    mock_info = MagicMock()
    mock_info.config.params.vectors.size = 384
    mock_info.config.params.vectors.distance = qmodels.Distance.COSINE
    mock_client.get_collection.return_value = mock_info

    service = QdrantService(url="http://mock-qdrant:6333", collection_name="test_collection")
    service.ensure_collection(dimension=384, distance_metric="Cosine")

    # Incompatible dimension should raise ValueError
    mock_info.config.params.vectors.size = 128
    with pytest.raises(ValueError, match="Incompatible vector dimension"):
        service.ensure_collection(dimension=384, distance_metric="Cosine")
