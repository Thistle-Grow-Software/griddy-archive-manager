from rest_framework.routers import DefaultRouter

from archive.api.viewsets.franchise import FranchiseViewSet
from archive.api.viewsets.league import LeagueViewSet
from archive.api.viewsets.org_unit import OrgUnitViewSet
from archive.api.viewsets.season import SeasonViewSet
from archive.api.viewsets.team import TeamViewSet
from archive.api.viewsets.team_affiliation import TeamAffiliationViewSet

router = DefaultRouter()
router.register("leagues", LeagueViewSet, basename="league")
router.register("seasons", SeasonViewSet, basename="season")
router.register("franchises", FranchiseViewSet, basename="franchise")
router.register("teams", TeamViewSet, basename="team")
router.register("org-units", OrgUnitViewSet, basename="orgunit")
router.register("team-affiliations", TeamAffiliationViewSet, basename="teamaffiliation")

urlpatterns = router.urls
