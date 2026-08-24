"""PULSE — Integration Tests for Static Tactical Cockpit & UI Asset Delivery (Phase 6.5).

Verifies the presentation layer delivery:
1. GET / and GET /ui serve the single-page application with valid HTML5 and MIME headers.
2. Complete DOM blueprint contracts (all 6 sub-component container IDs and critical elements).
3. Zero external CDN references in index.html (self-contained local assets only).
4. Static assets (style.css, app.js) serve correct MIME types and non-empty content.
5. Upstream match preflight routes and API docs remain unshadowed and healthy.

Authority: Phase 6.5 Decisions D-1, D-3, D-5, D-7, D-8, ADR-013, Gate 6.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app


@pytest.mark.asyncio
async def test_root_and_ui_endpoints_serve_html() -> None:
    """Verify GET / and GET /ui return HTTP 200 with text/html content-type."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in ["/", "/ui"]:
            response = await client.get(path)
            assert response.status_code == 200
            content_type = response.headers.get("content-type", "")
            assert "text/html" in content_type
            assert "<!DOCTYPE html>" in response.text
            assert "PULSE" in response.text


@pytest.mark.asyncio
async def test_html_contains_required_cockpit_dom_contracts() -> None:
    """Verify index.html contains all required container IDs across the 6 sub-components."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        html = response.text

        # Sub-Component 1: Scoreboard Header
        assert 'id="scoreboard"' in html
        assert 'id="match-title"' in html
        assert 'id="match-surface-badge"' in html
        assert 'id="server-indicator-p1"' in html
        assert 'id="score-sets-p1"' in html
        assert 'id="score-games-p1"' in html
        assert 'id="score-points-p1"' in html
        assert 'id="high-leverage-badge"' in html

        # Sub-Component 2: Oscillogram
        assert 'id="oscillogram-container"' in html
        assert 'id="leverage-canvas"' in html
        assert 'id="canvas-tooltip"' in html
        assert 'id="legend-container"' in html

        # Sub-Component 3: LangGraph Conditional Topology Inspector
        assert 'id="topology-inspector"' in html
        assert 'id="node-state-monitor"' in html
        assert 'id="node-pressure-diagnostic"' in html
        assert 'id="node-strategy-exploit"' in html
        assert 'id="node-tactical-output"' in html

        # Sub-Component 4: Game-Theoretic Exploit Panel
        assert 'id="game-theory-panel"' in html
        assert 'id="payoff-grid"' in html
        assert 'id="bar-nash"' in html
        assert 'id="bar-bias"' in html
        assert 'id="exploit-callout"' in html

        # Sub-Component 5: Tactical Advisory Feed
        assert 'id="tactical-feed"' in html
        assert 'id="tactical-headline"' in html
        assert 'id="tactical-narrative"' in html
        assert 'id="tactical-recommendation-list"' in html
        assert 'id="advisory-disclaimer"' in html

        # Sub-Component 6: Stream Control Bar
        assert 'id="stream-controls"' in html
        assert 'id="match-select"' in html
        assert 'id="speed-select"' in html
        assert 'id="btn-play"' in html
        assert 'id="btn-pause"' in html
        assert 'id="btn-reset"' in html
        assert 'id="stream-status-badge"' in html
        assert 'id="otel-trace-badge"' in html


@pytest.mark.asyncio
async def test_static_assets_serve_correct_mime_types() -> None:
    """Verify static assets (/static/style.css and /static/app.js) serve correct MIME types."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Style CSS
        css_resp = await client.get("/static/style.css")
        assert css_resp.status_code == 200
        css_content_type = css_resp.headers.get("content-type", "")
        assert "text/css" in css_content_type
        assert ":root" in css_resp.text
        assert "--bg-base" in css_resp.text

        # 2. App JS
        js_resp = await client.get("/static/app.js")
        assert js_resp.status_code == 200
        js_content_type = js_resp.headers.get("content-type", "")
        assert "javascript" in js_content_type
        assert "renderLeverageChart" in js_resp.text
        assert "startStream" in js_resp.text


@pytest.mark.asyncio
async def test_no_external_cdn_references() -> None:
    """Verify index.html contains 0 external CDN links (100% self-contained)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        html = response.text.lower()

        # Disallow external http/https CDN references
        assert "http://" not in html
        assert "https://" not in html
        assert "cdn." not in html
        assert "unpkg.com" not in html
        assert "jsdelivr" not in html
        assert "cdnjs" not in html
        assert "fonts.googleapis" not in html


@pytest.mark.asyncio
async def test_match_preflight_and_docs_route_precedence() -> None:
    """Verify API documentation and match routes maintain precedence alongside UI."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Matches list preflight
        matches_resp = await client.get("/v1/matches")
        assert matches_resp.status_code == 200
        matches_data = matches_resp.json()
        assert isinstance(matches_data, list)
        assert len(matches_data) > 0

        # Health endpoint
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] in ["healthy", "degraded"]

        # OpenAPI schema
        openapi_resp = await client.get("/openapi.json")
        assert openapi_resp.status_code == 200
        openapi_json = openapi_resp.json()
        assert "/v1/matches" in openapi_json["paths"]
        assert "/ui" in openapi_json["paths"]
