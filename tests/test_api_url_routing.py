"""Tests to verify API URL routing meets TGF-288 acceptance criteria."""

import pytest
from django.test import Client
from django.urls import resolve, reverse


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
def test_api_v1_url_resolves():
    """The /api/v1/ URL must resolve to the DRF router root."""
    match = resolve("/api/v1/")
    assert match is not None


@pytest.mark.django_db
def test_api_v1_returns_200(client):
    """GET /api/v1/ must return HTTP 200."""
    response = client.get("/api/v1/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200


@pytest.mark.django_db
def test_api_v1_returns_empty_router_response(client):
    """The API root must return an empty object (no registered endpoints yet)."""
    response = client.get("/api/v1/", HTTP_ACCEPT="application/json")
    assert response.json() == {}


@pytest.mark.django_db
def test_api_v1_browsable_api_available(client):
    """Requesting /api/v1/ with text/html should return the browsable API."""
    response = client.get("/api/v1/", HTTP_ACCEPT="text/html")
    assert response.status_code == 200
    assert "text/html" in response["Content-Type"]


@pytest.mark.django_db
def test_api_v1_url_is_included_in_urlconf():
    """The api/v1/ path must be present in the root URL configuration."""
    # reverse on the DRF api-root should produce /api/v1/
    url = reverse("api-root")
    assert url == "/api/v1/"
