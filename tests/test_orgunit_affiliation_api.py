"""Tests for OrgUnit and TeamAffiliation serializers and viewsets (TGF-291)."""

import pytest
from django.test import Client
from django.urls import reverse

from archive.api.serializers.org_unit import (
    OrgUnitDetailSerializer,
    OrgUnitListSerializer,
)
from archive.api.serializers.team_affiliation import (
    TeamAffiliationDetailSerializer,
    TeamAffiliationListSerializer,
)
from archive.models import (
    Franchise,
    League,
    OrgUnit,
    Season,
    Team,
    TeamAffiliation,
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
def afc(nfl):
    return OrgUnit.objects.create(
        league=nfl,
        short_name="AFC",
        long_name="American Football Conference",
        org_type="CONFERENCE",
    )


@pytest.fixture
def afc_north(nfl, afc):
    return OrgUnit.objects.create(
        league=nfl,
        short_name="AFCN",
        long_name="AFC North",
        org_type="DIVISION",
        parent=afc,
    )


@pytest.fixture
def afc_south(nfl, afc):
    return OrgUnit.objects.create(
        league=nfl,
        short_name="AFCS",
        long_name="AFC South",
        org_type="DIVISION",
        parent=afc,
    )


@pytest.fixture
def season_2024(nfl):
    return Season.objects.create(league=nfl, year=2024, label="2024")


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
    )


@pytest.fixture
def steelers_affiliation(steelers, afc_north, season_2024):
    return TeamAffiliation.objects.create(
        team=steelers, org_unit=afc_north, season=season_2024
    )


# --- OrgUnitListSerializer ---


@pytest.mark.django_db
def test_org_unit_list_serializer_fields(afc_north, nfl, afc):
    """OrgUnitListSerializer includes id, short_name, long_name, org_type, league, parent."""
    org = OrgUnit.objects.select_related("league", "parent").get(pk=afc_north.pk)
    serializer = OrgUnitListSerializer(org)
    data = serializer.data
    assert data["id"] == afc_north.pk
    assert data["short_name"] == "AFCN"
    assert data["long_name"] == "AFC North"
    assert data["org_type"] == "DIVISION"
    assert data["league"] == nfl.pk
    assert data["parent"] == afc.pk


# --- OrgUnitDetailSerializer ---


@pytest.mark.django_db
def test_org_unit_detail_serializer_includes_children(afc, afc_north, afc_south):
    """OrgUnitDetailSerializer includes all fields plus nested children."""
    org = OrgUnit.objects.prefetch_related("children").get(pk=afc.pk)
    serializer = OrgUnitDetailSerializer(org)
    data = serializer.data
    assert data["short_name"] == "AFC"
    assert data["parent"] is None
    assert "bonus_data" in data
    assert "external_ids" in data
    assert len(data["children"]) == 2
    child_names = {c["short_name"] for c in data["children"]}
    assert child_names == {"AFCN", "AFCS"}


# --- TeamAffiliationListSerializer ---


@pytest.mark.django_db
def test_affiliation_list_serializer_fields(
    steelers_affiliation, steelers, afc_north, season_2024
):
    """TeamAffiliationListSerializer includes id, team, org_unit, season."""
    aff = TeamAffiliation.objects.select_related("team", "org_unit", "season").get(
        pk=steelers_affiliation.pk
    )
    serializer = TeamAffiliationListSerializer(aff)
    data = serializer.data
    assert data["id"] == steelers_affiliation.pk
    assert data["team"] == steelers.pk
    assert data["org_unit"] == afc_north.pk
    assert data["season"] == season_2024.pk


# --- TeamAffiliationDetailSerializer ---


@pytest.mark.django_db
def test_affiliation_detail_serializer_all_fields(steelers_affiliation):
    """TeamAffiliationDetailSerializer includes all fields with temporal scoping."""
    aff = TeamAffiliation.objects.select_related("team", "org_unit", "season").get(
        pk=steelers_affiliation.pk
    )
    serializer = TeamAffiliationDetailSerializer(aff)
    data = serializer.data
    assert "start_date" in data
    assert "end_date" in data
    assert "bonus_data" in data
    assert "external_ids" in data


# --- OrgUnitViewSet endpoints ---


@pytest.mark.django_db
def test_org_unit_list_returns_200(client, afc_north):
    """GET /api/v1/org-units/ returns 200."""
    response = client.get("/api/v1/org-units/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_org_unit_filter_by_league(client, nfl, afc_north):
    """GET /api/v1/org-units/?league=<id> filters by league."""
    response = client.get(
        f"/api/v1/org-units/?league={nfl.pk}", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert all(r["league"] == nfl.pk for r in results)


@pytest.mark.django_db
def test_org_unit_filter_by_org_type(client, afc, afc_north, afc_south):
    """GET /api/v1/org-units/?org_type=DIVISION filters by type."""
    response = client.get(
        "/api/v1/org-units/?org_type=DIVISION", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 2
    assert all(r["org_type"] == "DIVISION" for r in results)


@pytest.mark.django_db
def test_org_unit_filter_by_parent(client, afc, afc_north, afc_south):
    """GET /api/v1/org-units/?parent=<id> filters by parent."""
    response = client.get(
        f"/api/v1/org-units/?parent={afc.pk}", HTTP_ACCEPT="application/json"
    )
    results = response.json()["results"]
    assert len(results) == 2


@pytest.mark.django_db
def test_org_unit_retrieve(client, afc, afc_north, afc_south):
    """GET /api/v1/org-units/<id>/ returns detail with nested children."""
    response = client.get(
        f"/api/v1/org-units/{afc.pk}/", HTTP_ACCEPT="application/json"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["short_name"] == "AFC"
    assert len(data["children"]) == 2


@pytest.mark.django_db
def test_org_unit_create(client, nfl):
    """POST /api/v1/org-units/ creates an org unit."""
    response = client.post(
        "/api/v1/org-units/",
        data={
            "short_name": "NFC",
            "long_name": "National Football Conference",
            "org_type": "CONFERENCE",
            "league": nfl.pk,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert OrgUnit.objects.filter(short_name="NFC").exists()


@pytest.mark.django_db
def test_org_unit_update(client, afc_north, nfl):
    """PUT /api/v1/org-units/<id>/ updates the org unit."""
    response = client.put(
        f"/api/v1/org-units/{afc_north.pk}/",
        data={
            "short_name": "AFCN",
            "long_name": "AFC North (Updated)",
            "org_type": "DIVISION",
            "league": nfl.pk,
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    afc_north.refresh_from_db()
    assert afc_north.long_name == "AFC North (Updated)"


@pytest.mark.django_db
def test_org_unit_delete_not_allowed(client, afc_north):
    """DELETE /api/v1/org-units/<id>/ is not supported."""
    response = client.delete(f"/api/v1/org-units/{afc_north.pk}/")
    assert response.status_code == 405


# --- TeamAffiliationViewSet endpoints ---


@pytest.mark.django_db
def test_affiliation_list_returns_200(client, steelers_affiliation):
    """GET /api/v1/team-affiliations/ returns 200."""
    response = client.get("/api/v1/team-affiliations/", HTTP_ACCEPT="application/json")
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.django_db
def test_affiliation_filter_by_team(client, steelers, steelers_affiliation):
    """GET /api/v1/team-affiliations/?team=<id> filters by team."""
    response = client.get(
        f"/api/v1/team-affiliations/?team={steelers.pk}",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["team"] == steelers.pk


@pytest.mark.django_db
def test_affiliation_filter_by_org_unit(client, afc_north, steelers_affiliation):
    """GET /api/v1/team-affiliations/?org_unit=<id> filters by org_unit."""
    response = client.get(
        f"/api/v1/team-affiliations/?org_unit={afc_north.pk}",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert len(results) == 1


@pytest.mark.django_db
def test_affiliation_filter_by_season(client, season_2024, steelers_affiliation):
    """GET /api/v1/team-affiliations/?season=<id> filters by season."""
    response = client.get(
        f"/api/v1/team-affiliations/?season={season_2024.pk}",
        HTTP_ACCEPT="application/json",
    )
    results = response.json()["results"]
    assert len(results) == 1


@pytest.mark.django_db
def test_affiliation_retrieve(client, steelers_affiliation):
    """GET /api/v1/team-affiliations/<id>/ returns detail."""
    response = client.get(
        f"/api/v1/team-affiliations/{steelers_affiliation.pk}/",
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert "start_date" in data
    assert "end_date" in data


@pytest.mark.django_db
def test_affiliation_create(client, steelers, afc_north, season_2024):
    """POST /api/v1/team-affiliations/ creates an affiliation."""
    # Delete the fixture-created one to avoid unique constraint
    TeamAffiliation.objects.all().delete()
    response = client.post(
        "/api/v1/team-affiliations/",
        data={
            "team": steelers.pk,
            "org_unit": afc_north.pk,
            "season": season_2024.pk,
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    assert TeamAffiliation.objects.filter(team=steelers, org_unit=afc_north).exists()


@pytest.mark.django_db
def test_affiliation_update(client, steelers_affiliation, steelers, afc_north):
    """PUT /api/v1/team-affiliations/<id>/ updates the affiliation."""
    response = client.put(
        f"/api/v1/team-affiliations/{steelers_affiliation.pk}/",
        data={
            "team": steelers.pk,
            "org_unit": afc_north.pk,
            "start_date": "2024-09-01",
            "end_date": "2025-02-09",
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    steelers_affiliation.refresh_from_db()
    assert str(steelers_affiliation.start_date) == "2024-09-01"


@pytest.mark.django_db
def test_affiliation_delete_not_allowed(client, steelers_affiliation):
    """DELETE /api/v1/team-affiliations/<id>/ is not supported."""
    response = client.delete(f"/api/v1/team-affiliations/{steelers_affiliation.pk}/")
    assert response.status_code == 405


# --- Router registration ---


@pytest.mark.django_db
def test_org_units_registered_on_router():
    """OrgUnitViewSet must be registered at /org-units/."""
    url = reverse("orgunit-list")
    assert url == "/api/v1/org-units/"


@pytest.mark.django_db
def test_team_affiliations_registered_on_router():
    """TeamAffiliationViewSet must be registered at /team-affiliations/."""
    url = reverse("teamaffiliation-list")
    assert url == "/api/v1/team-affiliations/"
