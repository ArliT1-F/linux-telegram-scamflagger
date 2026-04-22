from api import index as api_index
from registry import RegistryConfig


def _configure_temp_registry(tmp_path):
    api_index.registry_config = RegistryConfig(
        live_file=tmp_path / "live.txt",
        download_dir=tmp_path / "downloads",
        download_meta_file=tmp_path / "meta.json",
        cooldown_days=30,
    )


def test_health_endpoint():
    client = api_index.app.test_client()
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_analyze_endpoint_rejects_empty_message():
    client = api_index.app.test_client()
    response = client.post("/api/analyze", json={"message": "   "})

    assert response.status_code == 400
    assert "cannot be empty" in response.get_json()["error"]


def test_analyze_endpoint_accepts_valid_message():
    client = api_index.app.test_client()
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


def test_registry_download_available_before_any_publish(tmp_path):
    _configure_temp_registry(tmp_path)
    client = api_index.app.test_client()
    response = client.get("/api/registry/download")
    assert response.status_code == 200


def test_registry_publish_rate_limit_and_download_remains_available(tmp_path):
    _configure_temp_registry(tmp_path)
    client = api_index.app.test_client()

    # Add staged registry entry.
    add_entry = client.post(
        "/api/registry/entry",
        json={
            "name": "Scammer One",
            "identifier": "tg:123",
            "scam_type": "payment-redirect",
            "score": 88,
            "confidence": "HIGH",
        },
    )
    assert add_entry.status_code == 200

    first_publish = client.post("/api/registry/publish")
    assert first_publish.status_code == 200
    assert first_publish.get_json()["appended_entries"] >= 1

    second_publish = client.post("/api/registry/publish")
    assert second_publish.status_code == 429

    # Download should still always work.
    download = client.get("/api/registry/download")
    assert download.status_code == 200
