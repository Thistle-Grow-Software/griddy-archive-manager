from django.contrib import admin

from . import models

admin.site.register(models.League)
admin.site.register(models.Season)
admin.site.register(models.Team)
admin.site.register(models.OrgUnit)
admin.site.register(models.TeamAffiliation)
admin.site.register(models.Venue)
admin.site.register(models.Source)
admin.site.register(models.Acquisition)
admin.site.register(models.VideoAsset)
admin.site.register(models.Tag)
admin.site.register(models.AssetTag)
