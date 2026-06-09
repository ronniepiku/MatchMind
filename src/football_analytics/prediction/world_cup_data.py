"""World Cup tournament definitions — historical and upcoming group stage data.

Provides confirmed group compositions for FIFA World Cup tournaments.
Each tournament is defined with its teams, groups, and format parameters.
This module acts as a data source that can be extended in the future to
fetch from external APIs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorldCupGroup:
    """A group within a World Cup tournament."""

    name: str
    teams: list[str]


@dataclass
class WorldCupTournament:
    """A complete World Cup tournament definition."""

    id: str
    name: str
    year: int
    host: str
    total_teams: int
    groups: list[WorldCupGroup]
    teams_advancing_per_group: int = 2
    best_third_place_count: int = 0
    knockout_rounds: int = 4
    status: str = "completed"  # "completed" | "upcoming"

    @property
    def all_teams(self) -> list[str]:
        """Get all team names across all groups."""
        return [team for group in self.groups for team in group.teams]


def get_world_cup_2018() -> WorldCupTournament:
    """FIFA World Cup 2018 — Russia. 32 teams, 8 groups of 4."""
    return WorldCupTournament(
        id="wc_2018",
        name="FIFA World Cup 2018",
        year=2018,
        host="Russia",
        total_teams=32,
        teams_advancing_per_group=2,
        best_third_place_count=0,
        knockout_rounds=4,  # R16, QF, SF, Final
        status="completed",
        groups=[
            WorldCupGroup(name="Group A", teams=["Russia", "Saudi Arabia", "Egypt", "Uruguay"]),
            WorldCupGroup(name="Group B", teams=["Portugal", "Spain", "Morocco", "Iran"]),
            WorldCupGroup(name="Group C", teams=["France", "Australia", "Peru", "Denmark"]),
            WorldCupGroup(name="Group D", teams=["Argentina", "Iceland", "Croatia", "Nigeria"]),
            WorldCupGroup(name="Group E", teams=["Brazil", "Switzerland", "Costa Rica", "Serbia"]),
            WorldCupGroup(name="Group F", teams=["Germany", "Mexico", "Sweden", "South Korea"]),
            WorldCupGroup(name="Group G", teams=["Belgium", "Panama", "Tunisia", "England"]),
            WorldCupGroup(name="Group H", teams=["Poland", "Senegal", "Colombia", "Japan"]),
        ],
    )


def get_world_cup_2022() -> WorldCupTournament:
    """FIFA World Cup 2022 — Qatar. 32 teams, 8 groups of 4."""
    return WorldCupTournament(
        id="wc_2022",
        name="FIFA World Cup 2022",
        year=2022,
        host="Qatar",
        total_teams=32,
        teams_advancing_per_group=2,
        best_third_place_count=0,
        knockout_rounds=4,  # R16, QF, SF, Final
        status="completed",
        groups=[
            WorldCupGroup(name="Group A", teams=["Qatar", "Ecuador", "Senegal", "Netherlands"]),
            WorldCupGroup(name="Group B", teams=["England", "Iran", "United States", "Wales"]),
            WorldCupGroup(name="Group C", teams=["Argentina", "Saudi Arabia", "Mexico", "Poland"]),
            WorldCupGroup(name="Group D", teams=["France", "Australia", "Denmark", "Tunisia"]),
            WorldCupGroup(name="Group E", teams=["Spain", "Costa Rica", "Germany", "Japan"]),
            WorldCupGroup(name="Group F", teams=["Belgium", "Canada", "Morocco", "Croatia"]),
            WorldCupGroup(name="Group G", teams=["Brazil", "Serbia", "Switzerland", "Cameroon"]),
            WorldCupGroup(name="Group H", teams=["Portugal", "Ghana", "Uruguay", "South Korea"]),
        ],
    )


def get_world_cup_2026() -> WorldCupTournament:
    """FIFA World Cup 2026 — USA/Mexico/Canada. 48 teams, 12 groups of 4."""
    return WorldCupTournament(
        id="wc_2026",
        name="FIFA World Cup 2026",
        year=2026,
        host="United States / Mexico / Canada",
        total_teams=48,
        teams_advancing_per_group=2,
        best_third_place_count=8,
        knockout_rounds=5,  # R32, R16, QF, SF, Final
        status="upcoming",
        groups=[
            WorldCupGroup(name="Group A", teams=["Mexico", "South Africa", "South Korea", "Czech Republic"]),
            WorldCupGroup(name="Group B", teams=["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"]),
            WorldCupGroup(name="Group C", teams=["Brazil", "Morocco", "Haiti", "Scotland"]),
            WorldCupGroup(name="Group D", teams=["United States", "Paraguay", "Australia", "Turkey"]),
            WorldCupGroup(name="Group E", teams=["Germany", "Curaçao", "Ivory Coast", "Ecuador"]),
            WorldCupGroup(name="Group F", teams=["Netherlands", "Japan", "Sweden", "Tunisia"]),
            WorldCupGroup(name="Group G", teams=["Belgium", "Egypt", "Iran", "New Zealand"]),
            WorldCupGroup(name="Group H", teams=["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"]),
            WorldCupGroup(name="Group I", teams=["France", "Senegal", "Iraq", "Norway"]),
            WorldCupGroup(name="Group J", teams=["Argentina", "Algeria", "Austria", "Jordan"]),
            WorldCupGroup(name="Group K", teams=["Portugal", "DR Congo", "Uzbekistan", "Colombia"]),
            WorldCupGroup(name="Group L", teams=["England", "Croatia", "Ghana", "Panama"]),
        ],
    )


def get_all_world_cups() -> list[WorldCupTournament]:
    """Get all available World Cup tournament definitions."""
    return [
        get_world_cup_2018(),
        get_world_cup_2022(),
        get_world_cup_2026(),
    ]


def get_world_cup_by_id(tournament_id: str) -> WorldCupTournament | None:
    """Look up a World Cup tournament by its ID."""
    tournaments = {t.id: t for t in get_all_world_cups()}
    return tournaments.get(tournament_id)
