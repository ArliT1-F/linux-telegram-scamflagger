from api.index import app


def test_health_endpoint():
    client = app.test_client()
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_analyze_endpoint_rejects_empty_message():
    client = app.test_client()
    response = client.post("/api/analyze", json={"message": "   "})

    assert response.status_code == 400
    assert "cannot be empty" in response.get_json()["error"]


def test_analyze_endpoint_accepts_valid_message():
    client = app.test_client()
    response = client.post(
        "/api/analyze",
        json={"message": "Want premium content? Pay me on paypal and move to whatsapp"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["score"] >= 30
    assert data["confidence"] in {"MEDIUM", "HIGH"}
    assert isinstance(data["reasons"], list)
    assert data["should_save"] is True
