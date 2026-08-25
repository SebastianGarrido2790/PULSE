"""Unit tests for src/api/main.py (FastAPI app, static mounts, and health check)."""

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


def test_ui_and_static_routes_registered() -> None:
    """Verify that root, ui alias, static assets, and streaming routes are registered."""
    route_paths = [getattr(r, "path", None) for r in app.routes]
    assert "/" in route_paths
    assert "/ui" in route_paths
    assert "/health" in route_paths
    assert "/static" in route_paths

    from src.api.streaming import streaming_router

    streaming_paths = [getattr(r, "path", None) for r in streaming_router.routes]
    assert "/v1/matches" in streaming_paths
    assert "/v1/matches/{match_id}" in streaming_paths
    assert "/v1/matches/{match_id}/report" in streaming_paths
    assert "/v1/matches/{match_id}/stream" in streaming_paths
    assert "/v1/matches/{match_id}/ws" in streaming_paths
