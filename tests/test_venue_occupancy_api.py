"""Tests for Venue and TeamVenueOccupancy serializers and viewsets (TGF-292)."""

import pytest
from django.test import Client
from django.urls import reverse

from archive.api.serializers.team_venue_occupancy import (
    TeamVenueOccupancyListSerializer,
)
from archive.api.serializers.venue import (
    VenueDetailSerializer,
    VenueListSerializer,
    VenueReferenceSerializer,
)
from archive.models import (
    Franchise,
    League,
    Team,
    TeamVenueOccupancy,
    Venue,
)


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def nfl():
    return League.objects.create(
        short_name="NFL", long_name="National Football League", level="PRO"
    )


@pytest.fixture
def steelers_franchise(nfl):
    return Franchise.objects.create(name="Pittsburgh Steelers", league=nfl)


@pytest.fixture
def steelers(steelers_franchise):
    return Team.objects.create(
        franchise=steelers_franchise,
        name="Pittsburgh Steelers",
        short_name="PIT",
        city="Pittsburgh",
        state="PA",
    )


@pytest.fixture
def heinz_field():
    return Venue.objects.create(
        name="Heinz Field", city="Pittsburgh", state="PA", capacity=68400
    )


@pytest.fixture
def acrisure():
    return Venue.objects.create(
        name="Acrisure Stadium", city="Pittsburgh", state="PA", capacity=68400
    )


@pytest.fixture
def metlife():
    return Venue.objects.create(
        name="MetLife Stadium", city="East Rutherford", state="NJ", capacity=82500
    )


@pytest.fixture
def occupancy(steelers, heinz_field):
    return TeamVenueOccupancy.objects.create(
        team=steelers,
        venue=heinz_field,
        start_date="2001-08-18",
        end_date="2022-03-01",
    )


@pytest.fixture
def occupancy_current(steelers, acrisure):
    return TeamVenueOccupancy.objects.create(
        team=steelers,
        venue=acrisure,
        start_date="2022-03-01",
    )


# --- VenueReferenceSerializer ---


@pytest.mark.django_db
def test_venue_reference_serializer_fields(heinz_field):
    """VenueReferenceSerializer includes id and name only."""
    serializer = VenueReferenceSerializer(heinz_field)
    data = serializer.data
    assert set(data.keys()) == {"id", "name"}
    assert data["name"] == "Heinz Field"


# --- VenueListSerializer ---


@pytest.mark.django_db
def test_venue_list_serializer_fields(heinz_field):
    """VenueListSerializer includes id, name, city, state, capacity."""
    serializer = VenueListSerializer(heinz_field)
    data = serializer.data
    assert data["id"] == heinz_field.pk
    assert data["name"] == "Heinz Field"
    assert data["city"] == "Pittsburgh"
    assert data["state"] == "PA"
    assert data["capacity"] == 68400


# --- VenueDetailSerializer ---


@pytest.mark.django_db
def test_venue_detail_serializer_all_fields(heinz_field):
    """VenueDetailSerializer includes all fields."""
    serializer = VenueDetailSerializer(heinz_field)
    data = serializer.data
    assert data["name"] == "Heinz Field"
    assert data["country"] == "US"
    assert "bonus_data" in data
    assert "external_ids" in data


# --- TeamVenueOccupancyListSerializer ---


@pytest.mark.django_db
def test_occupancy_list_serializer_fields(occupancy, steelers, heinz_field):
    """TeamVenueOccupancyListSerializer includes id, team, venue, date range."""
    occ = TeamVenueOccupancy.objects.select_related("team", "venue").get(
        pk=occupancy.pk
    )
    serializer = TeamVenueOccupancyListSerializer(occ)
    data = serializer.data
    assert data["id"] == occupancy.pk
    assert data["team"] == steelers.pk
    assert data["venue"] == heinz_field.pk
    assert data["start_date"] == "2001-08-18"
    assert data["end_date"] == "2022-03-01"


# --- VenueViewSet endpoints ---


@pytest.mark.django_db
def test_venue_list_returns_200(client, heinz_field):
    """GET /api/v1/venues/ returns 200."""
    response = client.get("/api/v1/venues/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_venue_filter_by_city(client, heinz_field, metlife):
    """GET /api/v1/venues/?city=Pittsburgh filters by city."""
    response = client.get(
        "/api/v1/venues/?city=Pittsburgh", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["city"] == "Pittsburgh"


@pytest.mark.django_db
def test_venue_filter_by_state(client, heinz_field, metlife):
    """GET /api/v1/venues/?state=NJ filters by state."""
    response = client.get("/api/v1/venues/?state=NJ", HTTP_ACCEPT="application/json")
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["name"] == "MetLife Stadium"


@pytest.mark.django_db
def test_venue_search_by_name(client, heinz_field, metlife):
    """GET /api/v1/venues/?search=Heinz finds by name."""
    response = client.get(
        "/api/v1/venues/?search=Heinz", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["name"] == "Heinz Field"


@pytest.mark.django_db
def test_venue_search_by_city(client, heinz_field, metlife):
    """GET /api/v1/venues/?search=Rutherford finds by city."""
    response = client.get(
        "/api/v1/venues/?search=Rutherford", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["name"] == "MetLife Stadium"


@pytest.mark.django_db
def test_venue_retrieve(client, heinz_field):
    """GET /api/v1/venues/<id>/ returns detail."""
    response = client.get(
        f"/api/v1/venues/{heinz_field.pk}/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Heinz Field"
    assert "country" in data
    assert "bonus_data" in data


@pytest.mark.django_db
def test_venue_create(client):
    """POST /api/v1/venues/ creates a venue."""
    response = client.post(
        "/api/v1/venues/",
        data={
            "name": "Lambeau Field",
            "city": "Green Bay",
            "state": "WI",
            "capacity": 81441,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert Venue.objects.filter(name="Lambeau Field").exists()


@pytest.mark.django_db
def test_venue_update(client, heinz_field):
    """PUT /api/v1/venues/<id>/ updates the venue."""
    response = client.put(
        f"/api/v1/venues/{heinz_field.pk}/",
        data={
            "name": "Heinz Field",
            "city": "Pittsburgh",
            "state": "PA",
            "capacity": 68500,
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    heinz_field.refresh_from_db()
    assert heinz_field.capacity == 68500


@pytest.mark.django_db
def test_venue_delete_not_allowed(client, heinz_field):
    """DELETE /api/v1/venues/<id>/ is not supported."""
    response = client.delete(f"/api/v1/venues/{heinz_field.pk}/")
    assert response.status_code == 405


# --- TeamVenueOccupancyViewSet endpoints ---


@pytest.mark.django_db
def test_occupancy_list_returns_200(client, occupancy):
    """GET /api/v1/team-venue-occupancies/ returns 200."""
    response = client.get(
        "/api/v1/team-venue-occupancies/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_occupancy_filter_by_team(client, steelers, occupancy, occupancy_current):
    """GET /api/v1/team-venue-occupancies/?team=<id> filters by team."""
    response = client.get(
        f"/api/v1/team-venue-occupancies/?team={steelers.pk}",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert len(results) == 2


@pytest.mark.django_db
def test_occupancy_filter_by_venue(client, heinz_field, occupancy, occupancy_current):
    """GET /api/v1/team-venue-occupancies/?venue=<id> filters by venue."""
    response = client.get(
        f"/api/v1/team-venue-occupancies/?venue={heinz_field.pk}",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["venue"] == heinz_field.pk


@pytest.mark.django_db
def test_occupancy_retrieve(client, occupancy):
    """GET /api/v1/team-venue-occupancies/<id>/ returns detail."""
    response = client.get(
        f"/api/v1/team-venue-occupancies/{occupancy.pk}/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["start_date"] == "2001-08-18"
    assert "bonus_data" in data


@pytest.mark.django_db
def test_occupancy_create(client, steelers, metlife):
    """POST /api/v1/team-venue-occupancies/ creates an occupancy."""
    response = client.post(
        "/api/v1/team-venue-occupancies/",
        data={
            "team": steelers.pk,
            "venue": metlife.pk,
            "start_date": "2025-01-01",
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert TeamVenueOccupancy.objects.filter(team=steelers, venue=metlife).exists()


@pytest.mark.django_db
def test_occupancy_update(client, occupancy, steelers, heinz_field):
    """PUT /api/v1/team-venue-occupancies/<id>/ updates the occupancy."""
    response = client.put(
        f"/api/v1/team-venue-occupancies/{occupancy.pk}/",
        data={
            "team": steelers.pk,
            "venue": heinz_field.pk,
            "start_date": "2001-08-18",
            "end_date": "2022-06-01",
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    occupancy.refresh_from_db()
    assert str(occupancy.end_date) == "2022-06-01"


@pytest.mark.django_db
def test_occupancy_delete_not_allowed(client, occupancy):
    """DELETE /api/v1/team-venue-occupancies/<id>/ is not supported."""
    response = client.delete(f"/api/v1/team-venue-occupancies/{occupancy.pk}/")
    assert response.status_code == 405


# --- Router registration ---


@pytest.mark.django_db
def test_venues_registered_on_router():
    """VenueViewSet must be registered at /venues/."""
    url = reverse("venue-list")
    assert url == "/api/v1/venues/"


@pytest.mark.django_db
def test_team_venue_occupancies_registered_on_router():
    """TeamVenueOccupancyViewSet must be registered at /team-venue-occupancies/."""
    url = reverse("teamvenueoccupancy-list")
    assert url == "/api/v1/team-venue-occupancies/"
