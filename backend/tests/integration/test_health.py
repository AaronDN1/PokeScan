from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_independent_capabilities_without_failing_api() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ready", "degraded"}
    assert body["database"] == "ready"
    assert isinstance(body["recognition_ready"], bool)
    assert "ocr" in body["capabilities"]
    assert "artwork_matching" in body["capabilities"]
    assert "catalog" in body["capabilities"]
    assert "pricing" in body["capabilities"]
