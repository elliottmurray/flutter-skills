from fastapi.testclient import TestClient

from main import app


def test_health_ok_when_app_check_disabled():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
