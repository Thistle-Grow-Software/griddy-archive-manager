"""Tests for Franchise and Team serializers and viewsets (TGF-290)."""

import pytest
from django.test import Client
from django.urls import reverse

from archive.api.serializers.franchise import (
    FranchiseDetailSerializer,
    FranchiseListSerializer,
)
from archive.api.serializers.team import (
    TeamDetailSerializer,
    TeamListSerializer,
    TeamReferenceSerializer,
    TeamWriteSerializer,
)
from archive.models import (
    Franchise,
    League,
    OrgUnit,
    Season,
    Team,
    TeamAffiliation,
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
def ravens_franchise(nfl):
    return Franchise.objects.create(name="Baltimore Ravens", league=nfl)


@pytest.fixture
def steelers(steelers_franchise):
    return Team.objects.create(
        franchise=steelers_franchise,
        name="Pittsburgh Steelers",
        short_name="PIT",
        city="Pittsburgh",
        state="PA",
        primary_color="FFB612",
        secondary_color="101820",
        mascot="Steely McBeam",
    )


@pytest.fixture
def ravens(ravens_franchise):
    return Team.objects.create(
        franchise=ravens_franchise,
        name="Baltimore Ravens",
        short_name="BAL",
        city="Baltimore",
        state="MD",
        primary_color="241773",
        secondary_color="000000",
    )


@pytest.fixture
def heinz_field():
    return Venue.objects.create(
        name="Heinz Field", city="Pittsburgh", state="PA", capacity=68400
    )


@pytest.fixture
def steelers_venue_occupancy(steelers, heinz_field):
    return TeamVenueOccupancy.objects.create(
        team=steelers, venue=heinz_field, start_date="2001-08-18"
    )


@pytest.fixture
def afc_north(nfl):
    return OrgUnit.objects.create(
        league=nfl, short_name="AFCN", long_name="AFC North", org_type="DIVISION"
    )


@pytest.fixture
def season_2024(nfl):
    return Season.objects.create(league=nfl, year=2024, label="2024")


@pytest.fixture
def steelers_affiliation(steelers, afc_north, season_2024):
    return TeamAffiliation.objects.create(
        team=steelers, org_unit=afc_north, season=season_2024
    )


# --- TeamReferenceSerializer ---


@pytest.mark.django_db
def test_team_reference_serializer_fields(steelers):
    """TeamReferenceSerializer includes id, name, short_name only."""
    serializer = TeamReferenceSerializer(steelers)
    data = serializer.data
    assert set(data.keys()) == {"id", "name", "short_name"}
    assert data["name"] == "Pittsburgh Steelers"
    assert data["short_name"] == "PIT"


# --- FranchiseListSerializer ---


@pytest.mark.django_db
def test_franchise_list_serializer_fields(steelers_franchise, nfl):
    """FranchiseListSerializer includes id, name, league."""
    franchise = Franchise.objects.select_related("league").get(pk=steelers_franchise.pk)
    serializer = FranchiseListSerializer(franchise)
    data = serializer.data
    assert data["id"] == steelers_franchise.pk
    assert data["name"] == "Pittsburgh Steelers"
    assert data["league"] == nfl.pk


# --- FranchiseDetailSerializer ---


@pytest.mark.django_db
def test_franchise_detail_serializer_includes_teams(steelers_franchise, steelers):
    """FranchiseDetailSerializer includes all fields plus nested teams."""
    franchise = Franchise.objects.prefetch_related("teams").get(
        pk=steelers_franchise.pk
    )
    serializer = FranchiseDetailSerializer(franchise)
    data = serializer.data
    assert data["name"] == "Pittsburgh Steelers"
    assert "bonus_data" in data
    assert "external_ids" in data
    assert len(data["teams"]) == 1
    assert data["teams"][0]["short_name"] == "PIT"


# --- TeamListSerializer ---


@pytest.mark.django_db
def test_team_list_serializer_fields(steelers, steelers_franchise):
    """TeamListSerializer includes id, name, short_name, city, state, franchise, colors."""
    team = Team.objects.select_related("franchise").get(pk=steelers.pk)
    serializer = TeamListSerializer(team)
    data = serializer.data
    assert data["id"] == steelers.pk
    assert data["name"] == "Pittsburgh Steelers"
    assert data["short_name"] == "PIT"
    assert data["city"] == "Pittsburgh"
    assert data["state"] == "PA"
    assert data["franchise"] == steelers_franchise.pk
    assert data["primary_color"] == "FFB612"
    assert data["secondary_color"] == "101820"


# --- TeamDetailSerializer ---


@pytest.mark.django_db
def test_team_detail_serializer_all_fields(
    steelers, steelers_affiliation, steelers_venue_occupancy
):
    """TeamDetailSerializer includes all fields plus nested affiliations and venue_occupancies."""
    team = (
        Team.objects.select_related("franchise")
        .prefetch_related("affiliations", "venue_occupancies")
        .get(pk=steelers.pk)
    )
    serializer = TeamDetailSerializer(team)
    data = serializer.data
    assert data["name"] == "Pittsburgh Steelers"
    assert data["mascot"] == "Steely McBeam"
    assert "bonus_data" in data
    assert "external_ids" in data
    assert len(data["affiliations"]) == 1
    assert len(data["venue_occupancies"]) == 1


# --- TeamWriteSerializer ---


@pytest.mark.django_db
def test_team_write_serializer_accepts_franchise_pk(steelers_franchise):
    """TeamWriteSerializer accepts integer PK for franchise FK."""
    serializer = TeamWriteSerializer(
        data={
            "franchise": steelers_franchise.pk,
            "name": "Pittsburgh Maulers",
            "short_name": "MAU",
        }
    )
    assert serializer.is_valid(), serializer.errors
    team = serializer.save()
    assert team.franchise == steelers_franchise


# --- FranchiseViewSet endpoints ---


@pytest.mark.django_db
def test_franchise_list_returns_200(client, steelers_franchise):
    """GET /api/v1/franchises/ returns 200."""
    response = client.get("/api/v1/franchises/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_franchise_filter_by_league(client, nfl, steelers_franchise):
    """GET /api/v1/franchises/?league=<id> filters by league."""
    ncaa = League.objects.create(
        short_name="NCAA",
        long_name="National Collegiate Athletic Association",
        level="COLLEGE",
    )
    Franchise.objects.create(name="Georgia Bulldogs", league=ncaa)
    response = client.get(
        f"/api/v1/franchises/?league={nfl.pk}", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["name"] == "Pittsburgh Steelers"


@pytest.mark.django_db
def test_franchise_retrieve(client, steelers_franchise, steelers):
    """GET /api/v1/franchises/<id>/ returns detail with nested teams."""
    response = client.get(
        f"/api/v1/franchises/{steelers_franchise.pk}/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Pittsburgh Steelers"
    assert len(data["teams"]) == 1


@pytest.mark.django_db
def test_franchise_create(client, nfl):
    """POST /api/v1/franchises/ creates a franchise."""
    response = client.post(
        "/api/v1/franchises/",
        data={"name": "Cleveland Browns", "league": nfl.pk},
        content_type="application/json",
    )
    assert response.status_code == 201
    assert Franchise.objects.filter(name="Cleveland Browns").exists()


@pytest.mark.django_db
def test_franchise_update(client, steelers_franchise, nfl):
    """PUT /api/v1/franchises/<id>/ updates the franchise."""
    response = client.put(
        f"/api/v1/franchises/{steelers_franchise.pk}/",
        data={"name": "Pittsburgh Steelers (Updated)", "league": nfl.pk},
        content_type="application/json",
    )
    assert response.status_code == 200
    steelers_franchise.refresh_from_db()
    assert steelers_franchise.name == "Pittsburgh Steelers (Updated)"


@pytest.mark.django_db
def test_franchise_delete_not_allowed(client, steelers_franchise):
    """DELETE /api/v1/franchises/<id>/ is not supported."""
    response = client.delete(f"/api/v1/franchises/{steelers_franchise.pk}/")
    assert response.status_code == 405


# --- TeamViewSet endpoints ---


@pytest.mark.django_db
def test_team_list_returns_200(client, steelers):
    """GET /api/v1/teams/ returns 200."""
    response = client.get("/api/v1/teams/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_team_filter_by_franchise(client, steelers, ravens):
    """GET /api/v1/teams/?franchise=<id> filters by franchise."""
    response = client.get(
        f"/api/v1/teams/?franchise={steelers.franchise.pk}",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["name"] == "Pittsburgh Steelers"


@pytest.mark.django_db
def test_team_filter_by_city(client, steelers, ravens):
    """GET /api/v1/teams/?city=Pittsburgh filters by city."""
    response = client.get(
        "/api/v1/teams/?city=Pittsburgh", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["city"] == "Pittsburgh"


@pytest.mark.django_db
def test_team_filter_by_state(client, steelers, ravens):
    """GET /api/v1/teams/?state=PA filters by state."""
    response = client.get("/api/v1/teams/?state=PA", HTTP_ACCEPT="application/json")
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["state"] == "PA"


@pytest.mark.django_db
def test_team_search_by_name(client, steelers, ravens):
    """GET /api/v1/teams/?search=Steelers finds by name."""
    response = client.get(
        "/api/v1/teams/?search=Steelers", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["name"] == "Pittsburgh Steelers"


@pytest.mark.django_db
def test_team_search_by_mascot(client, steelers, ravens):
    """GET /api/v1/teams/?search=Steely finds by mascot."""
    response = client.get(
        "/api/v1/teams/?search=Steely", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["name"] == "Pittsburgh Steelers"


@pytest.mark.django_db
def test_team_retrieve_returns_detail(
    client, steelers, steelers_affiliation, steelers_venue_occupancy
):
    """GET /api/v1/teams/<id>/ returns detail with nested affiliations and venues."""
    response = client.get(
        f"/api/v1/teams/{steelers.pk}/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Pittsburgh Steelers"
    assert data["mascot"] == "Steely McBeam"
    assert len(data["affiliations"]) == 1
    assert len(data["venue_occupancies"]) == 1


@pytest.mark.django_db
def test_team_create(client, steelers_franchise):
    """POST /api/v1/teams/ creates a team."""
    response = client.post(
        "/api/v1/teams/",
        data={
            "franchise": steelers_franchise.pk,
            "name": "Pittsburgh Maulers",
            "short_name": "MAU",
            "city": "Pittsburgh",
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert Team.objects.filter(name="Pittsburgh Maulers").exists()


@pytest.mark.django_db
def test_team_update(client, steelers, steelers_franchise):
    """PUT /api/v1/teams/<id>/ updates the team."""
    response = client.put(
        f"/api/v1/teams/{steelers.pk}/",
        data={
            "franchise": steelers_franchise.pk,
            "name": "Pittsburgh Steelers",
            "short_name": "PIT",
            "city": "Pittsburgh",
            "state": "PA",
            "mascot": "Steely McBeam Jr.",
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    steelers.refresh_from_db()
    assert steelers.mascot == "Steely McBeam Jr."


@pytest.mark.django_db
def test_team_delete_not_allowed(client, steelers):
    """DELETE /api/v1/teams/<id>/ is not supported."""
    response = client.delete(f"/api/v1/teams/{steelers.pk}/")
    assert response.status_code == 405


# --- N+1 query prevention ---


@pytest.mark.django_db
def test_team_list_uses_select_related(
    client, steelers, ravens, django_assert_num_queries
):
    """Team list should not produce N+1 queries."""
    # 1 query: teams JOIN franchise + 2 prefetches (affiliations, venue_occupancies)
    with django_assert_num_queries(3):
        client.get("/api/v1/teams/", HTTP_ACCEPT="application/json")


# --- Router registration ---


@pytest.mark.django_db
def test_franchises_registered_on_router():
    """FranchiseViewSet must be registered at /franchises/."""
    url = reverse("franchise-list")
    assert url == "/api/v1/franchises/"


@pytest.mark.django_db
def test_teams_registered_on_router():
    """TeamViewSet must be registered at /teams/."""
    url = reverse("team-list")
    assert url == "/api/v1/teams/"
