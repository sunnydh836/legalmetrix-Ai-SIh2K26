def test_root_endpoint(client):
    """Verify root endpoint status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data == {"name": "LegalMetrix AI API", "status": "running"}


def test_health_endpoint(client):
    """Verify health endpoint status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "healthy"}


def test_v1_health_endpoint(client):
    """Verify v1 health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "healthy"}


def test_config_loading(app_settings):
    """Verify core configuration loaded properly."""
    assert app_settings.APP_NAME == "LegalMetrix AI"
    assert app_settings.API_V1_STR == "/api/v1"
    assert len(app_settings.CORS_ORIGINS) > 0
