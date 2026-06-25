"""Tests for the FastAPI application factory and health endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    """Create a test application instance."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client):
    """Health check endpoint returns healthy status."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "smart-wifi-dashboard"


@pytest.mark.asyncio
async def test_cors_headers(client):
    """CORS middleware adds appropriate headers for allowed origins."""
    response = await client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_app_metadata(app):
    """Application has correct metadata from settings."""
    assert app.title == "Smart WiFi Dashboard"
    assert app.version == "0.1.0"
