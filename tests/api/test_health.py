"""API tests for health endpoints."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "healthy"
    assert "X-Request-ID" in response.headers


def test_health_accepts_incoming_request_id(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "test-request-id"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"


def test_health_database_endpoint(client: TestClient) -> None:
    with patch(
        "app.health.service.check_database_connection",
        new_callable=AsyncMock,
        return_value=True,
    ):
        response = client.get("/health/database")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["component"] == "database"
    assert body["data"]["status"] == "healthy"


def test_health_redis_endpoint(client: TestClient) -> None:
    with patch(
        "app.infrastructure.redis.client.RedisClient.health_check",
        new_callable=AsyncMock,
        return_value=True,
    ):
        response = client.get("/health/redis")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["component"] == "redis"


def test_health_storage_endpoint(client: TestClient) -> None:
    response = client.get("/health/storage")
    assert response.status_code in {200, 503}
    body = response.json()
    assert body["success"] is True
    assert body["data"]["component"] == "storage"
