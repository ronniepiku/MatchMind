"""Integration tests for the FastAPI REST API layer.

Tests endpoint logic without requiring a live database — uses mocking
for DB-dependent endpoints and exercises logic-only endpoints directly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from football_analytics.api import app

client = TestClient(app, raise_server_exceptions=False)


# ============================================================================
# Health & Readiness
# ============================================================================


class TestHealthEndpoint:
    """Tests for /api/v1/health."""

    def test_returns_200(self) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_response_structure(self) -> None:
        data = client.get("/api/v1/health").json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_version_matches_package(self) -> None:
        import football_analytics

        data = client.get("/api/v1/health").json()
        assert data["version"] == football_analytics.__version__


class TestReadinessEndpoint:
    """Tests for /api/v1/ready."""

    @patch("football_analytics.db.check_connectivity", return_value=True)
    def test_ready_when_db_connected(self, mock_conn: MagicMock) -> None:
        response = client.get("/api/v1/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    @patch("football_analytics.db.check_connectivity", return_value=False)
    def test_not_ready_when_db_down(self, mock_conn: MagicMock) -> None:
        response = client.get("/api/v1/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"


# ============================================================================
# Security Headers
# ============================================================================


class TestSecurityHeaders:
    """Verify security headers are present on all responses."""

    def test_x_content_type_options(self) -> None:
        response = client.get("/api/v1/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self) -> None:
        response = client.get("/api/v1/health")
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_x_xss_protection(self) -> None:
        response = client.get("/api/v1/health")
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_request_id_assigned(self) -> None:
        response = client.get("/api/v1/health")
        assert "X-Request-ID" in response.headers
        # Should be a UUID format
        assert len(response.headers["X-Request-ID"]) == 36

    def test_request_id_echoed(self) -> None:
        custom_id = "test-request-123"
        response = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
        assert response.headers["X-Request-ID"] == custom_id


# ============================================================================
# xG Prediction Endpoint
# ============================================================================


class TestXGPrediction:
    """Tests for /api/v1/xg/predict."""

    def test_basic_shot_prediction(self) -> None:
        payload = {
            "location_x": 108.0,
            "location_y": 40.0,
            "shot_body_part": "Foot",
            "under_pressure": False,
            "play_pattern": "From Open Play",
        }
        response = client.post("/api/v1/xg/predict", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert 0.0 <= data["xg"] <= 1.0
        assert data["distance_to_goal"] >= 0
        assert data["goal_angle"] >= 0
        assert isinstance(data["features_used"], dict)

    def test_penalty_shot_high_xg(self) -> None:
        payload = {
            "location_x": 108.0,
            "location_y": 40.0,
            "shot_body_part": "Foot",
            "under_pressure": False,
            "play_pattern": "From Penalty",
            "shot_type": "Penalty",
        }
        response = client.post("/api/v1/xg/predict", json=payload)
        data = response.json()
        # Penalties should have xG > 0.7
        assert data["xg"] > 0.7

    def test_header_under_pressure_lower_xg(self) -> None:
        base_payload = {
            "location_x": 105.0,
            "location_y": 40.0,
            "shot_body_part": "Foot",
            "under_pressure": False,
            "play_pattern": "From Open Play",
        }
        pressure_payload = {**base_payload, "shot_body_part": "Head", "under_pressure": True}

        base_response = client.post("/api/v1/xg/predict", json=base_payload).json()
        pressure_response = client.post("/api/v1/xg/predict", json=pressure_payload).json()

        assert pressure_response["xg"] < base_response["xg"]

    def test_invalid_coordinates_rejected(self) -> None:
        payload = {
            "location_x": 150.0,  # > 120
            "location_y": 40.0,
        }
        response = client.post("/api/v1/xg/predict", json=payload)
        assert response.status_code == 422

    def test_missing_required_fields(self) -> None:
        response = client.post("/api/v1/xg/predict", json={})
        assert response.status_code == 422


# ============================================================================
# Simulation Endpoint
# ============================================================================


class TestMatchSimulation:
    """Tests for /api/v1/simulation/match-direct."""

    def test_basic_simulation(self) -> None:
        payload = {
            "home_xg": 1.8,
            "away_xg": 1.2,
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "n_simulations": 1000,
        }
        response = client.post("/api/v1/simulation/match-direct", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Probabilities should sum to ~1.0
        prob_sum = data["home_win_prob"] + data["draw_prob"] + data["away_win_prob"]
        assert abs(prob_sum - 1.0) < 0.01

        assert data["home_team"] == "Arsenal"
        assert data["away_team"] == "Chelsea"
        assert data["n_simulations"] == 1000
        assert isinstance(data["most_likely_score"], list)
        assert len(data["most_likely_score"]) == 2
        assert isinstance(data["top_scorelines"], dict)

    def test_home_advantage_increases_home_win(self) -> None:
        base = {
            "home_xg": 1.5,
            "away_xg": 1.5,
            "n_simulations": 5000,
            "home_advantage_factor": 1.0,
        }
        boosted = {**base, "home_advantage_factor": 1.5}

        base_result = client.post("/api/v1/simulation/match-direct", json=base).json()
        boosted_result = client.post("/api/v1/simulation/match-direct", json=boosted).json()

        assert boosted_result["home_win_prob"] > base_result["home_win_prob"]

    def test_invalid_xg_rejected(self) -> None:
        payload = {"home_xg": 0, "away_xg": 1.0}  # gt=0 constraint
        response = client.post("/api/v1/simulation/match-direct", json=payload)
        assert response.status_code == 422

    def test_over_under_probabilities_consistent(self) -> None:
        payload = {"home_xg": 2.5, "away_xg": 2.0, "n_simulations": 5000}
        data = client.post("/api/v1/simulation/match-direct", json=payload).json()

        # Over thresholds should be decreasing
        assert data["over_1_5_prob"] >= data["over_2_5_prob"]
        assert data["over_2_5_prob"] >= data["over_3_5_prob"]


# ============================================================================
# Error Handling
# ============================================================================


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_404_on_unknown_route(self) -> None:
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    def test_method_not_allowed(self) -> None:
        response = client.delete("/api/v1/health")
        assert response.status_code == 405

    def test_cors_header_present(self) -> None:
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should allow the configured origin
        assert response.status_code == 200
