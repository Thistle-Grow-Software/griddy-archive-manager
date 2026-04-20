from rest_framework.routers import DefaultRouter

from archive.api.viewsets.league import LeagueViewSet
from archive.api.viewsets.season import SeasonViewSet

router = DefaultRouter()
router.register("leagues", LeagueViewSet, basename="league")
router.register("seasons", SeasonViewSet, basename="season")

urlpatterns = router.urls
