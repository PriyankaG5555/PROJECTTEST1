from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_path_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/nope").status_code == 404
