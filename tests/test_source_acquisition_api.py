"""Tests for Source and Acquisition serializers and viewsets (TGF-302)."""

import pytest
from django.test import Client
from django.urls import reverse

from archive.api.serializers.acquisition import (
    AcquisitionDetailSerializer,
    AcquisitionListSerializer,
)
from archive.api.serializers.source import SourceDetailSerializer, SourceListSerializer
from archive.models import Acquisition, Source


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def nfl_plus():
    return Source.objects.create(
        name="NFL+",
        source_type="STREAMING",
        url="https://www.nfl.com/plus/",
        notes="NFL streaming service",
    )


@pytest.fixture
def youtube():
    return Source.objects.create(
        name="YouTube",
        source_type="YOUTUBE",
        url="https://youtube.com",
    )


@pytest.fixture
def acquisition1(nfl_plus):
    return Acquisition.objects.create(
        source=nfl_plus,
        acquired_on="2024-09-01",
        cost_usd="14.99",
        rights="PERSONAL_ONLY",
        notes="Monthly subscription",
    )


@pytest.fixture
def acquisition2(youtube):
    return Acquisition.objects.create(
        source=youtube,
        acquired_on="2024-09-15",
        rights="SHAREABLE",
    )


# --- SourceListSerializer ---


@pytest.mark.django_db
def test_source_list_serializer_fields(nfl_plus):
    """SourceListSerializer includes id, name, source_type, url."""
    data = SourceListSerializer(nfl_plus).data
    assert data["id"] == nfl_plus.pk
    assert data["name"] == "NFL+"
    assert data["source_type"] == "STREAMING"
    assert data["url"] == "https://www.nfl.com/plus/"


# --- SourceDetailSerializer ---


@pytest.mark.django_db
def test_source_detail_serializer_all_fields(nfl_plus):
    """SourceDetailSerializer includes all fields."""
    data = SourceDetailSerializer(nfl_plus).data
    assert data["notes"] == "NFL streaming service"
    assert "bonus_data" in data
    assert "external_ids" in data


# --- AcquisitionListSerializer ---


@pytest.mark.django_db
def test_acquisition_list_serializer_fields(acquisition1, nfl_plus):
    """AcquisitionListSerializer includes id, source, acquired_on, rights, cost_usd."""
    acq = Acquisition.objects.select_related("source").get(pk=acquisition1.pk)
    data = AcquisitionListSerializer(acq).data
    assert data["id"] == acquisition1.pk
    assert data["source"] == nfl_plus.pk
    assert data["acquired_on"] == "2024-09-01"
    assert data["rights"] == "PERSONAL_ONLY"
    assert data["cost_usd"] == "14.99"


# --- AcquisitionDetailSerializer ---


@pytest.mark.django_db
def test_acquisition_detail_serializer_all_fields(acquisition1):
    """AcquisitionDetailSerializer includes all fields."""
    acq = Acquisition.objects.select_related("source").get(pk=acquisition1.pk)
    data = AcquisitionDetailSerializer(acq).data
    assert data["notes"] == "Monthly subscription"
    assert "proof_path" in data
    assert "bonus_data" in data


# --- SourceViewSet: Full CRUD ---


@pytest.mark.django_db
def test_source_list(client, nfl_plus, youtube):
    """GET /api/v1/sources/ returns sources."""
    response = client.get("/api/v1/sources/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    assert "results" in response.json()
    assert len(response.json()["results"]) == 2


@pytest.mark.django_db
def test_source_retrieve(client, nfl_plus):
    """GET /api/v1/sources/<id>/ returns detail."""
    response = client.get(
        f"/api/v1/sources/{nfl_plus.pk}/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    assert response.json()["notes"] == "NFL streaming service"


@pytest.mark.django_db
def test_source_create(client):
    """POST /api/v1/sources/ creates a source."""
    response = client.post(
        "/api/v1/sources/",
        data={"name": "Paramount+", "source_type": "STREAMING"},
        content_type="application/json",
    )
    assert response.status_code == 201
    assert Source.objects.filter(name="Paramount+").exists()


@pytest.mark.django_db
def test_source_update(client, nfl_plus):
    """PUT /api/v1/sources/<id>/ updates the source."""
    response = client.put(
        f"/api/v1/sources/{nfl_plus.pk}/",
        data={"name": "NFL+ Premium", "source_type": "STREAMING"},
        content_type="application/json",
    )
    assert response.status_code == 200
    nfl_plus.refresh_from_db()
    assert nfl_plus.name == "NFL+ Premium"


@pytest.mark.django_db
def test_source_delete(client, nfl_plus):
    """DELETE /api/v1/sources/<id>/ deletes the source."""
    response = client.delete(f"/api/v1/sources/{nfl_plus.pk}/")
    assert response.status_code == 204
    assert not Source.objects.filter(pk=nfl_plus.pk).exists()


# --- AcquisitionViewSet: Full CRUD ---


@pytest.mark.django_db
def test_acquisition_list(client, acquisition1, acquisition2):
    """GET /api/v1/acquisitions/ returns acquisitions."""
    response = client.get("/api/v1/acquisitions/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


@pytest.mark.django_db
def test_acquisition_retrieve(client, acquisition1):
    """GET /api/v1/acquisitions/<id>/ returns detail."""
    response = client.get(
        f"/api/v1/acquisitions/{acquisition1.pk}/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    assert response.json()["notes"] == "Monthly subscription"


@pytest.mark.django_db
def test_acquisition_create(client, nfl_plus):
    """POST /api/v1/acquisitions/ creates an acquisition."""
    response = client.post(
        "/api/v1/acquisitions/",
        data={
            "source": nfl_plus.pk,
            "acquired_on": "2024-10-01",
            "rights": "PERSONAL_ONLY",
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert Acquisition.objects.filter(acquired_on="2024-10-01").exists()


@pytest.mark.django_db
def test_acquisition_update(client, acquisition1, nfl_plus):
    """PUT /api/v1/acquisitions/<id>/ updates the acquisition."""
    response = client.put(
        f"/api/v1/acquisitions/{acquisition1.pk}/",
        data={
            "source": nfl_plus.pk,
            "acquired_on": "2024-09-01",
            "rights": "SHAREABLE",
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    acquisition1.refresh_from_db()
    assert acquisition1.rights == "SHAREABLE"


@pytest.mark.django_db
def test_acquisition_delete(client, acquisition1):
    """DELETE /api/v1/acquisitions/<id>/ deletes the acquisition."""
    response = client.delete(f"/api/v1/acquisitions/{acquisition1.pk}/")
    assert response.status_code == 204
    assert not Acquisition.objects.filter(pk=acquisition1.pk).exists()


# --- Acquisition Filters ---


@pytest.mark.django_db
def test_acquisition_filter_by_source(client, acquisition1, acquisition2, nfl_plus):
    """?source=<id> filters by source."""
    response = client.get(
        f"/api/v1/acquisitions/?source={nfl_plus.pk}",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["source"] == nfl_plus.pk


@pytest.mark.django_db
def test_acquisition_filter_by_rights(client, acquisition1, acquisition2):
    """?rights=SHAREABLE filters by rights."""
    response = client.get(
        "/api/v1/acquisitions/?rights=SHAREABLE", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["rights"] == "SHAREABLE"


# --- Router registration ---


@pytest.mark.django_db
def test_sources_registered_on_router():
    """SourceViewSet must be registered at /sources/."""
    url = reverse("source-list")
    assert url == "/api/v1/sources/"


@pytest.mark.django_db
def test_acquisitions_registered_on_router():
    """AcquisitionViewSet must be registered at /acquisitions/."""
    url = reverse("acquisition-list")
    assert url == "/api/v1/acquisitions/"
