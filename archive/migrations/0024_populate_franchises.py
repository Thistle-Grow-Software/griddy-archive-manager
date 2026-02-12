"""
Data migration: create Franchise records from existing Teams and link them.

- NFL teams: Franchise name = team.mascot ("Steelers", "Raiders")
- CFB/other teams: Franchise name = team.name ("Georgia", "Air Force")
- League determined from team's affiliations -> org_unit -> league
"""

from django.db import migrations


def _resolve_league(team, league_cache):
    """Determine the league for a team using affiliations, external_ids, or school_name."""
    # 1. From affiliations (most reliable)
    affiliation = team.affiliations.select_related("org_unit__league").first()
    if affiliation:
        return affiliation.org_unit.league

    # 2. NFL teams without affiliations (e.g. Arizona Cardinals) have nfl.com external_ids
    if team.external_ids and "nfl.com" in team.external_ids:
        return league_cache.get("NFL")

    # 3. College teams without affiliations (FCS) have school_name set
    if team.school_name:
        return league_cache.get("NCAA - FCS")

    return None


def create_franchises(apps, schema_editor):
    Team = apps.get_model("archive", "Team")
    Franchise = apps.get_model("archive", "Franchise")
    League = apps.get_model("archive", "League")

    league_cache = {lg.short_name: lg for lg in League.objects.all()}

    for team in Team.objects.all():
        league = _resolve_league(team, league_cache)
        if league is None:
            continue

        # NFL teams use mascot; others use team name
        if league.short_name == "NFL" and team.mascot:
            franchise_name = team.mascot
        else:
            franchise_name = team.name

        franchise, _ = Franchise.objects.get_or_create(
            league=league,
            name=franchise_name,
        )
        team.franchise = franchise
        team.save(update_fields=["franchise"])


def reverse_franchises(apps, schema_editor):
    Team = apps.get_model("archive", "Team")
    Franchise = apps.get_model("archive", "Franchise")

    Team.objects.update(franchise=None)
    Franchise.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("archive", "0023_add_franchise_model"),
    ]

    operations = [
        migrations.RunPython(create_franchises, reverse_franchises),
    ]
