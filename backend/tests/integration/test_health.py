from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_missing_model_artifacts_without_failing_api() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"] == "ready"
    assert body["models"] in {"ready", "artifacts_required"}
