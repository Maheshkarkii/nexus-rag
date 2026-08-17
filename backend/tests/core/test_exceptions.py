"""Tests for custom application exception hierarchy and standardized error envelopes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
    ServiceException,
    ValidationException,
    register_exception_handlers,
)


def test_exception_properties() -> None:
    """Verify AppException subclasses initialize with proper default codes and HTTP status codes."""
    not_found = NotFoundException(message="Item missing", details={"id": 42})
    assert not_found.status_code == 404
    assert not_found.code == "NOT_FOUND"
    assert not_found.message == "Item missing"
    assert not_found.details == {"id": 42}

    bad_req = BadRequestException(message="Invalid format")
    assert bad_req.status_code == 400
    assert bad_req.code == "BAD_REQUEST"

    validation = ValidationException(message="Email invalid")
    assert validation.status_code == 422
    assert validation.code == "VALIDATION_ERROR"

    service_err = ServiceException(message="Qdrant connection timed out")
    assert service_err.status_code == 503
    assert service_err.code == "SERVICE_UNAVAILABLE"


def test_custom_exception_handler_integration() -> None:
    """Verify that an application endpoint raising an AppException produces the standard envelope."""
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/trigger-error")
    def trigger_error():
        raise BadRequestException(
            message="Malformed query parameters",
            details={"field": "query", "issue": "cannot be blank"},
        )

    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.get("/trigger-error")
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "BAD_REQUEST"
    assert data["error"]["message"] == "Malformed query parameters"
    assert data["error"]["details"] == {"field": "query", "issue": "cannot be blank"}
