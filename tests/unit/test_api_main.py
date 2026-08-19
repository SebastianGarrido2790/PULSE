"""Unit tests for src/api/main.py (FastAPI app, lifespan initialization, and health check)."""

from fastapi.testclient import TestClient

from src.api.main import app


def test_health_endpoint_with_lifespan() -> None:
    """Verify that GET /health returns healthy status and graph readiness under lifespan context."""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200

        payload = response.json()
        assert payload["status"] == "healthy"
        assert payload["graph_ready"] is True
        assert payload["version"] == "0.1.0"
        assert len(payload["artifacts_loaded"]) == 3
        assert "stratum_table" in payload["artifacts_loaded"]
        assert "pressure_model_artifact" in payload["artifacts_loaded"]
        assert "payoff_matrices" in payload["artifacts_loaded"]


def test_health_endpoint_degraded_when_no_graph() -> None:
    """Verify GET /health returns degraded status if graph is not loaded."""
    client = TestClient(app, raise_server_exceptions=False)
    # Outside lifespan context manager, app.state.graph is not initialized
    response = client.get("/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["graph_ready"] is False
