from django.contrib import admin

from . import models


class TeamInline(admin.TabularInline):
    model = models.Team
    fk_name = "franchise"
    fields = ("name", "city", "short_name", "era_start_date", "era_end_date")
    extra = 0


@admin.register(models.Franchise)
class FranchiseAdmin(admin.ModelAdmin):
    list_display = ("name", "league")
    list_filter = ("league",)
    search_fields = ("name",)
    inlines = [TeamInline]


@admin.register(models.Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "franchise", "era_start_date", "era_end_date")
    list_filter = ("franchise__league",)
    search_fields = ("name",)
    raw_id_fields = ("franchise",)


admin.site.register(models.League)
admin.site.register(models.Season)
admin.site.register(models.OrgUnit)
admin.site.register(models.TeamAffiliation)
admin.site.register(models.Venue)
admin.site.register(models.Source)
admin.site.register(models.Acquisition)
admin.site.register(models.VideoAsset)
admin.site.register(models.Tag)
admin.site.register(models.AssetTag)
admin.site.register(models.QuarterScore)
admin.site.register(models.TeamStandingsSnapshot)
admin.site.register(models.Drive)
admin.site.register(models.Play)
admin.site.register(models.PlayStat)
admin.site.register(models.PassingBoxscore)
admin.site.register(models.RushingBoxscore)
admin.site.register(models.ReceivingBoxscore)
admin.site.register(models.TacklesBoxscore)
admin.site.register(models.FumblesBoxscore)
admin.site.register(models.FieldGoalsBoxscore)
admin.site.register(models.ExtraPointsBoxscore)
admin.site.register(models.KickingBoxscore)
admin.site.register(models.PuntingBoxscore)
admin.site.register(models.ReturnBoxscore)
admin.site.register(models.GameReplay)
