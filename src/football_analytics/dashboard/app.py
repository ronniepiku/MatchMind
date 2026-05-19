"""Interactive Football Analytics Dashboard — Plotly Dash.

Two main views:
1. Opponent Profile — Pre-match scouting report with attack patterns,
   defensive shape, and key player threats.
2. Player Performance — Individual player metrics, rolling form, and
   radar comparison charts.

Run: `uv run fb-dashboard` or `uv run python -m football_analytics.dashboard.app`
"""

from __future__ import annotations

import logging

import dash
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html

from football_analytics.analysis.opponent_profile import build_opponent_report
from football_analytics.analysis.player_performance import (
    get_player_rolling_form,
    get_player_season_summary,
    get_squad_comparison,
)
from football_analytics.dashboard.data_helpers import (
    check_data_availability,
    get_available_players,
    get_available_seasons,
    get_available_teams,
)
from football_analytics.db import get_engine

logger = logging.getLogger(__name__)

# =============================================================================
# APP INITIALISATION
# =============================================================================

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True,
    title="MatchMind — Football Analytics",
)

# =============================================================================
# LAYOUT
# =============================================================================

# Navigation bar
navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Opponent Profile", href="/opponent")),
        dbc.NavItem(dbc.NavLink("Player Performance", href="/player")),
        dbc.NavItem(dbc.NavLink("Team Scorecard", href="/scorecard")),
    ],
    brand="MatchMind Analytics",
    brand_href="/",
    color="primary",
    dark=True,
)

# Page content container
app.layout = dbc.Container(
    [
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="store-teams", storage_type="session"),
        dcc.Store(id="store-seasons", storage_type="session"),
        navbar,
        html.Br(),
        html.Div(id="page-content"),
    ],
    fluid=True,
)


# =============================================================================
# PAGE: OPPONENT PROFILE
# =============================================================================

opponent_layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H2("Opponent Scouting Report", className="mb-3"),
                        html.P(
                            "Select a team and season to generate a pre-match scouting report with "
                            "attack patterns, defensive shape, and key player threats.",
                            className="text-muted",
                        ),
                        html.Hr(),
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        dbc.Label(
                                            "Team", html_for="opponent-team-dropdown"
                                        ),
                                        dcc.Dropdown(
                                            id="opponent-team-dropdown",
                                            placeholder="Search for a team...",
                                            searchable=True,
                                            clearable=True,
                                        ),
                                    ],
                                    md=4,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Label(
                                            "Season",
                                            html_for="opponent-season-dropdown",
                                        ),
                                        dcc.Dropdown(
                                            id="opponent-season-dropdown",
                                            placeholder="Select a season...",
                                            searchable=True,
                                            clearable=True,
                                        ),
                                    ],
                                    md=5,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Button(
                                            "Generate Report",
                                            id="btn-opponent-report",
                                            color="primary",
                                            className="mt-4 w-100",
                                            disabled=True,
                                        ),
                                    ],
                                    md=3,
                                ),
                            ]
                        ),
                    ]
                ),
            ]
        ),
        html.Br(),
        # Status / feedback area
        html.Div(id="opponent-status", className="mb-3"),
        # Loading spinner wrapping results
        dcc.Loading(
            id="loading-opponent",
            type="default",
            children=[
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Attack Patterns"),
                                        dbc.CardBody(id="opponent-attack-table"),
                                    ]
                                ),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Defensive Shape by Zone"),
                                        dbc.CardBody(id="opponent-defense-chart"),
                                    ]
                                ),
                            ],
                            md=6,
                        ),
                    ]
                ),
                html.Br(),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Key Players (by xG + xA)"),
                                        dbc.CardBody(id="opponent-key-players"),
                                    ]
                                ),
                            ]
                        ),
                    ]
                ),
            ],
        ),
    ]
)


# =============================================================================
# PAGE: PLAYER PERFORMANCE
# =============================================================================

player_layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H2("Player Performance Dashboard", className="mb-3"),
                        html.P(
                            "Select a player, team, and season to view individual metrics, "
                            "rolling form, and squad comparisons.",
                            className="text-muted",
                        ),
                        html.Hr(),
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        dbc.Label(
                                            "Team", html_for="player-team-dropdown"
                                        ),
                                        dcc.Dropdown(
                                            id="player-team-dropdown",
                                            placeholder="Search for a team...",
                                            searchable=True,
                                            clearable=True,
                                        ),
                                    ],
                                    md=3,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Label(
                                            "Season", html_for="player-season-dropdown"
                                        ),
                                        dcc.Dropdown(
                                            id="player-season-dropdown",
                                            placeholder="Select a season...",
                                            searchable=True,
                                            clearable=True,
                                        ),
                                    ],
                                    md=4,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Label("Player", html_for="player-dropdown"),
                                        dcc.Dropdown(
                                            id="player-dropdown",
                                            placeholder="Select a player...",
                                            searchable=True,
                                            clearable=True,
                                        ),
                                    ],
                                    md=3,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Button(
                                            "Analyse",
                                            id="btn-player-analyse",
                                            color="primary",
                                            className="mt-4 w-100",
                                            disabled=True,
                                        ),
                                    ],
                                    md=2,
                                ),
                            ]
                        ),
                    ]
                ),
            ]
        ),
        html.Br(),
        html.Div(id="player-status", className="mb-3"),
        dcc.Loading(
            id="loading-player",
            type="default",
            children=[
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Season Summary"),
                                        dbc.CardBody(id="player-summary-table"),
                                    ]
                                ),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Rolling Form (xG & xA)"),
                                        dbc.CardBody(
                                            dcc.Graph(id="player-rolling-chart")
                                        ),
                                    ]
                                ),
                            ],
                            md=6,
                        ),
                    ]
                ),
                html.Br(),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Squad Comparison"),
                                        dbc.CardBody(id="squad-comparison-table"),
                                    ]
                                ),
                            ]
                        ),
                    ]
                ),
            ],
        ),
    ]
)


# =============================================================================
# PAGE: TEAM PERFORMANCE SCORECARD
# =============================================================================

scorecard_layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H2("Team Performance Scorecard", className="mb-3"),
                        html.P(
                            "Holistic team performance overview: possession quality, "
                            "pressing intensity, set-piece efficiency, and trends.",
                            className="text-muted",
                        ),
                        html.Hr(),
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        dbc.Label("Team", html_for="sc-team-dropdown"),
                                        dcc.Dropdown(
                                            id="sc-team-dropdown",
                                            placeholder="Search for a team...",
                                            searchable=True,
                                            clearable=True,
                                        ),
                                    ],
                                    md=5,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Label(
                                            "Season", html_for="sc-season-dropdown"
                                        ),
                                        dcc.Dropdown(
                                            id="sc-season-dropdown",
                                            placeholder="Select a season...",
                                            searchable=True,
                                            clearable=True,
                                        ),
                                    ],
                                    md=5,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Button(
                                            "Generate",
                                            id="btn-scorecard",
                                            color="primary",
                                            className="mt-4 w-100",
                                            disabled=True,
                                        ),
                                    ],
                                    md=2,
                                ),
                            ]
                        ),
                    ]
                ),
            ]
        ),
        html.Br(),
        html.Div(id="sc-status", className="mb-3"),
        dcc.Loading(
            id="loading-scorecard",
            type="default",
            children=[
                # KPI cards row
                dbc.Row(id="sc-kpi-row", className="mb-3"),
                # Charts row
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Possession Style Distribution"),
                                        dbc.CardBody(
                                            dcc.Graph(id="sc-possession-chart")
                                        ),
                                    ]
                                ),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Defensive Pressing by Zone"),
                                        dbc.CardBody(dcc.Graph(id="sc-pressing-chart")),
                                    ]
                                ),
                            ],
                            md=6,
                        ),
                    ]
                ),
                html.Br(),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Set-Piece Efficiency"),
                                        dbc.CardBody(id="sc-setpiece-table"),
                                    ]
                                ),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Transition Metrics"),
                                        dbc.CardBody(id="sc-transition-table"),
                                    ]
                                ),
                            ],
                            md=6,
                        ),
                    ]
                ),
            ],
        ),
    ]
)


# =============================================================================
# HOME PAGE
# =============================================================================

home_layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H1("MatchMind Analytics", className="text-center mt-4"),
                        html.P(
                            "StatsBomb open-data powered analysis for coaches, analysts, and scouts.",
                            className="text-center text-muted",
                        ),
                        html.Hr(),
                        dbc.Row(
                            [
                                dbc.Col(
                                    dbc.Card(
                                        [
                                            dbc.CardBody(
                                                [
                                                    html.H4(
                                                        "Opponent Profile",
                                                        className="card-title",
                                                    ),
                                                    html.P(
                                                        "Pre-match scouting: attack patterns, "
                                                        "defensive shape, key threats."
                                                    ),
                                                    dbc.Button(
                                                        "Open",
                                                        href="/opponent",
                                                        color="primary",
                                                        outline=True,
                                                    ),
                                                ]
                                            ),
                                        ],
                                        className="h-100",
                                    ),
                                    md=6,
                                ),
                                dbc.Col(
                                    dbc.Card(
                                        [
                                            dbc.CardBody(
                                                [
                                                    html.H4(
                                                        "Player Performance",
                                                        className="card-title",
                                                    ),
                                                    html.P(
                                                        "Individual metrics, rolling form, and radar comparisons."
                                                    ),
                                                    dbc.Button(
                                                        "Open",
                                                        href="/player",
                                                        color="primary",
                                                        outline=True,
                                                    ),
                                                ]
                                            ),
                                        ],
                                        className="h-100",
                                    ),
                                    md=6,
                                ),
                            ]
                        ),
                        html.Br(),
                        dbc.Row(
                            [
                                dbc.Col(
                                    dbc.Card(
                                        [
                                            dbc.CardBody(
                                                [
                                                    html.H4(
                                                        "Team Scorecard",
                                                        className="card-title",
                                                    ),
                                                    html.P(
                                                        "Holistic performance: possession, "
                                                        "pressing, set-pieces, transitions."
                                                    ),
                                                    dbc.Button(
                                                        "Open",
                                                        href="/scorecard",
                                                        color="primary",
                                                        outline=True,
                                                    ),
                                                ]
                                            ),
                                        ],
                                        className="h-100",
                                    ),
                                    md=6,
                                ),
                            ]
                        ),
                        html.Br(),
                        dbc.Alert(
                            [
                                html.I(className="bi bi-info-circle-fill me-2"),
                                "Select a section above to begin analysis. "
                                "Data is sourced from StatsBomb open data — "
                                "ensure you have run the ingestion pipeline "
                                "(uv run fb-ingest) before generating reports.",
                            ],
                            color="info",
                            className="mt-3",
                        ),
                    ]
                ),
            ]
        ),
    ]
)


# =============================================================================
# ROUTING
# =============================================================================


@callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname: str) -> html.Div:
    """Route URL to page layout."""
    if pathname == "/opponent":
        return opponent_layout
    elif pathname == "/player":
        return player_layout
    elif pathname == "/scorecard":
        return scorecard_layout
    return home_layout


# =============================================================================
# CALLBACKS: POPULATE DROPDOWNS
# =============================================================================


@callback(
    Output("opponent-team-dropdown", "options"),
    Input("url", "pathname"),
)
def populate_opponent_teams(pathname: str) -> list:
    """Load available teams when navigating to opponent page."""
    if pathname != "/opponent":
        return dash.no_update
    try:
        engine = get_engine()
        return get_available_teams(engine)
    except Exception:
        return []


@callback(
    Output("opponent-season-dropdown", "options"),
    Input("url", "pathname"),
)
def populate_opponent_seasons(pathname: str) -> list:
    """Load available seasons when navigating to opponent page."""
    if pathname != "/opponent":
        return dash.no_update
    try:
        engine = get_engine()
        return get_available_seasons(engine)
    except Exception:
        return []


@callback(
    Output("btn-opponent-report", "disabled"),
    [
        Input("opponent-team-dropdown", "value"),
        Input("opponent-season-dropdown", "value"),
    ],
)
def toggle_opponent_button(team_id, season_id) -> bool:
    """Enable the Generate button only when both team and season are selected."""
    return not (team_id and season_id)


@callback(
    Output("player-team-dropdown", "options"),
    Input("url", "pathname"),
)
def populate_player_teams(pathname: str) -> list:
    """Load available teams for the player page."""
    if pathname != "/player":
        return dash.no_update
    try:
        engine = get_engine()
        return get_available_teams(engine)
    except Exception:
        return []


@callback(
    Output("player-season-dropdown", "options"),
    Input("url", "pathname"),
)
def populate_player_seasons(pathname: str) -> list:
    """Load available seasons for the player page."""
    if pathname != "/player":
        return dash.no_update
    try:
        engine = get_engine()
        return get_available_seasons(engine)
    except Exception:
        return []


@callback(
    Output("player-dropdown", "options"),
    [Input("player-team-dropdown", "value"), Input("player-season-dropdown", "value")],
)
def populate_players(team_id, season_id) -> list:
    """Load available players when team and season are selected."""
    if not team_id and not season_id:
        return []
    try:
        engine = get_engine()
        return get_available_players(engine, team_id=team_id, season_id=season_id)
    except Exception:
        return []


@callback(
    Output("btn-player-analyse", "disabled"),
    [
        Input("player-dropdown", "value"),
        Input("player-team-dropdown", "value"),
        Input("player-season-dropdown", "value"),
    ],
)
def toggle_player_button(player_id, team_id, season_id) -> bool:
    """Enable the Analyse button only when player, team, and season are selected."""
    return not (player_id and team_id and season_id)


# =============================================================================
# CALLBACKS: OPPONENT PROFILE
# =============================================================================


@callback(
    [
        Output("opponent-attack-table", "children"),
        Output("opponent-defense-chart", "children"),
        Output("opponent-key-players", "children"),
        Output("opponent-status", "children"),
    ],
    Input("btn-opponent-report", "n_clicks"),
    [
        State("opponent-team-dropdown", "value"),
        State("opponent-season-dropdown", "value"),
    ],
    prevent_initial_call=True,
)
def update_opponent_report(
    n_clicks: int | None,
    team_id: int | None,
    season_id: int | None,
) -> tuple:
    """Generate opponent scouting report on button click."""
    if not team_id or not season_id:
        msg = dbc.Alert("Please select both a team and a season.", color="warning")
        return "", "", "", msg

    try:
        engine = get_engine()

        # Check data availability first
        availability = check_data_availability(engine, team_id, season_id)
        if not availability["available"]:
            msg = dbc.Alert(
                [
                    html.Strong("No data available. "),
                    availability["message"],
                ],
                color="warning",
            )
            return "", "", "", msg

        report = build_opponent_report(team_id, season_id, engine)

        # Attack patterns table
        if not report["attack_patterns"].empty:
            attack_table = dbc.Table.from_dataframe(
                report["attack_patterns"],
                striped=True,
                bordered=True,
                hover=True,
                size="sm",
            )
        else:
            attack_table = html.P(
                "No attack pattern data found.", className="text-muted"
            )

        # Defensive shape bar chart
        if not report["defensive_shape"].empty:
            defense_fig = px.bar(
                report["defensive_shape"],
                x="zone",
                y=["pressures", "tackles", "interceptions"],
                barmode="group",
                title="Defensive Actions by Zone",
                template="plotly_white",
                color_discrete_sequence=["#2c3e50", "#18bc9c", "#3498db"],
            )
            defense_fig.update_layout(
                legend_title_text="Action Type",
                xaxis_title="Pitch Zone",
                yaxis_title="Count",
            )
            defense_chart = dcc.Graph(figure=defense_fig)
        else:
            defense_chart = html.P("No defensive data found.", className="text-muted")

        # Key players table
        if not report["key_players"].empty:
            key_players_table = dbc.Table.from_dataframe(
                report["key_players"],
                striped=True,
                bordered=True,
                hover=True,
                size="sm",
            )
        else:
            key_players_table = html.P(
                "No key player data found.", className="text-muted"
            )

        status = dbc.Alert(
            f"Report generated successfully — {availability['match_count']} matches analysed.",
            color="success",
            dismissable=True,
        )
        return attack_table, defense_chart, key_players_table, status

    except Exception as e:
        logger.exception("Error generating opponent report")
        error_msg = dbc.Alert(
            [html.Strong("Error: "), str(e)],
            color="danger",
        )
        return "", "", "", error_msg


# =============================================================================
# CALLBACKS: PLAYER PERFORMANCE
# =============================================================================


@callback(
    [
        Output("player-summary-table", "children"),
        Output("player-rolling-chart", "figure"),
        Output("squad-comparison-table", "children"),
        Output("player-status", "children"),
    ],
    Input("btn-player-analyse", "n_clicks"),
    [
        State("player-dropdown", "value"),
        State("player-team-dropdown", "value"),
        State("player-season-dropdown", "value"),
    ],
    prevent_initial_call=True,
)
def update_player_performance(
    n_clicks: int | None,
    player_id: int | None,
    team_id: int | None,
    season_id: int | None,
) -> tuple:
    """Generate player performance analysis on button click."""
    empty_fig = go.Figure()
    empty_fig.update_layout(
        template="plotly_white",
        annotations=[
            {
                "text": "No data to display",
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {"size": 16, "color": "gray"},
            }
        ],
    )

    if not player_id or not season_id:
        msg = dbc.Alert("Please select a player and season.", color="warning")
        return "", empty_fig, "", msg

    try:
        engine = get_engine()

        # Check data availability
        availability = check_data_availability(engine, team_id, season_id)
        if not availability["available"]:
            msg = dbc.Alert(
                [
                    html.Strong("No data available. "),
                    availability["message"],
                ],
                color="warning",
            )
            return "", empty_fig, "", msg

        # Season summary
        summary = get_player_season_summary(engine, player_id, season_id)
        if not summary.empty:
            summary_table = dbc.Table.from_dataframe(
                summary.T.reset_index().rename(columns={"index": "Metric", 0: "Value"}),
                striped=True,
                bordered=True,
                size="sm",
            )
        else:
            summary_table = html.P(
                "No summary data for this player/season.",
                className="text-muted",
            )

        # Rolling form chart
        rolling = get_player_rolling_form(engine, player_id, season_id)
        if not rolling.empty:
            rolling_fig = px.line(
                rolling,
                x="match_date",
                y=["rolling_xg", "rolling_xa"],
                title="Rolling 5-Match xG & xA",
                markers=True,
                template="plotly_white",
                labels={
                    "value": "Expected Value",
                    "match_date": "Match Date",
                    "variable": "Metric",
                },
                color_discrete_map={"rolling_xg": "#2c3e50", "rolling_xa": "#18bc9c"},
            )
            rolling_fig.update_layout(legend_title_text="Metric")
        else:
            rolling_fig = empty_fig

        # Squad comparison
        if team_id:
            squad = get_squad_comparison(engine, team_id, season_id)
            squad_table = (
                dbc.Table.from_dataframe(
                    squad, striped=True, bordered=True, hover=True, size="sm"
                )
                if not squad.empty
                else html.P("No squad data available.", className="text-muted")
            )
        else:
            squad_table = html.P(
                "Select a team to view squad comparison.", className="text-muted"
            )

        status = dbc.Alert(
            f"Analysis complete — {availability['match_count']} matches analysed.",
            color="success",
            dismissable=True,
        )
        return summary_table, rolling_fig, squad_table, status

    except Exception as e:
        logger.exception("Error generating player analysis")
        error_msg = dbc.Alert(
            [html.Strong("Error: "), str(e)],
            color="danger",
        )
        return "", empty_fig, "", error_msg


# =============================================================================
# CALLBACKS: TEAM SCORECARD
# =============================================================================


@callback(
    Output("sc-team-dropdown", "options"),
    Input("url", "pathname"),
)
def populate_sc_teams(pathname: str) -> list:
    """Load available teams for scorecard page."""
    if pathname != "/scorecard":
        return dash.no_update
    try:
        engine = get_engine()
        return get_available_teams(engine)
    except Exception:
        return []


@callback(
    Output("sc-season-dropdown", "options"),
    Input("url", "pathname"),
)
def populate_sc_seasons(pathname: str) -> list:
    """Load available seasons for scorecard page."""
    if pathname != "/scorecard":
        return dash.no_update
    try:
        engine = get_engine()
        return get_available_seasons(engine)
    except Exception:
        return []


@callback(
    Output("btn-scorecard", "disabled"),
    [Input("sc-team-dropdown", "value"), Input("sc-season-dropdown", "value")],
)
def toggle_sc_button(team_id, season_id) -> bool:
    """Enable scorecard button when both selections made."""
    return not (team_id and season_id)


@callback(
    [
        Output("sc-kpi-row", "children"),
        Output("sc-possession-chart", "figure"),
        Output("sc-pressing-chart", "figure"),
        Output("sc-setpiece-table", "children"),
        Output("sc-transition-table", "children"),
        Output("sc-status", "children"),
    ],
    Input("btn-scorecard", "n_clicks"),
    [
        State("sc-team-dropdown", "value"),
        State("sc-season-dropdown", "value"),
    ],
    prevent_initial_call=True,
)
def update_scorecard(
    n_clicks: int | None,
    team_id: int | None,
    season_id: int | None,
) -> tuple:
    """Generate the team performance scorecard."""
    import pandas as pd
    from sqlalchemy import text

    empty_fig = go.Figure()
    empty_fig.update_layout(template="plotly_white")

    if not team_id or not season_id:
        msg = dbc.Alert("Please select a team and season.", color="warning")
        return [], empty_fig, empty_fig, "", "", msg

    try:
        engine = get_engine()

        # Check data availability
        availability = check_data_availability(engine, team_id, season_id)
        if not availability["available"]:
            msg = dbc.Alert(
                [html.Strong("No data available. "), availability["message"]],
                color="warning",
            )
            return [], empty_fig, empty_fig, "", "", msg

        # --- Possession profile ---
        with engine.connect() as conn:
            events_df = pd.read_sql(
                text("""
                    SELECT e.*
                    FROM events e
                    JOIN matches m ON e.match_id = m.match_id
                    WHERE e.team_id = :team_id
                      AND m.season_id = :season_id
                    ORDER BY e.match_id, e.minute, e.second
                """),
                conn,
                params={"team_id": team_id, "season_id": season_id},
            )

        from football_analytics.analysis.possession_chains import (
            chains_to_dataframe,
            compute_team_possession_profile,
            compute_transition_metrics,
            extract_possession_chains,
        )

        chains = extract_possession_chains(events_df)
        chains_df = chains_to_dataframe(chains)
        profile = compute_team_possession_profile(chains_df, team_id)
        transitions = compute_transition_metrics(chains)

        # --- KPI cards ---
        kpi_data = [
            (
                "Dangerous Possession %",
                f"{profile.get('dangerous_possession_rate', 0) * 100:.1f}%",
            ),
            ("Box Entry Rate", f"{profile.get('box_entry_rate', 0) * 100:.1f}%"),
            ("xG per Chain", f"{profile.get('xg_per_chain', 0):.3f}"),
            ("Total xG", f"{profile.get('total_xg_from_chains', 0):.1f}"),
            ("Avg Passes/Chain", f"{profile.get('avg_passes_per_chain', 0):.1f}"),
        ]
        kpi_cards = [
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                html.H6(label, className="text-muted mb-1"),
                                html.H4(value, className="mb-0"),
                            ]
                        ),
                    ],
                    className="text-center",
                ),
                md=True,
            )
            for label, value in kpi_data
        ]

        # --- Possession style pie chart ---
        style_dist = profile.get("style_distribution", {})
        if style_dist:
            style_df = pd.DataFrame(
                list(style_dist.items()),
                columns=["Style", "Proportion"],
            )
            possession_fig = px.pie(
                style_df,
                names="Style",
                values="Proportion",
                title="Build-Up Style Breakdown",
                template="plotly_white",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
        else:
            possession_fig = empty_fig

        # --- Pressing / defensive shape chart ---
        from football_analytics.analysis.opponent_profile import (
            get_opponent_defensive_shape,
        )

        defense_df = get_opponent_defensive_shape(engine, team_id, season_id)
        if not defense_df.empty:
            pressing_fig = px.bar(
                defense_df,
                x="zone",
                y=["pressures", "tackles", "interceptions"],
                barmode="group",
                title="Defensive Actions by Zone",
                template="plotly_white",
                color_discrete_sequence=["#2c3e50", "#18bc9c", "#3498db"],
            )
        else:
            pressing_fig = empty_fig

        # --- Set-piece table ---
        from football_analytics.analysis.set_pieces import (
            compute_set_piece_efficiency,
            extract_set_pieces,
            set_pieces_to_dataframe,
        )

        with engine.connect() as conn:
            sp_events = pd.read_sql(
                text("""
                    SELECT e.*, p.player_name
                    FROM events e
                    LEFT JOIN players p
                        ON e.player_id = p.player_id
                    JOIN matches m ON e.match_id = m.match_id
                    WHERE e.team_id = :team_id
                      AND m.season_id = :season_id
                      AND e.play_pattern IN (
                          'From Corner', 'From Free Kick',
                          'From Throw In'
                      )
                """),
                conn,
                params={"team_id": team_id, "season_id": season_id},
            )

        if not sp_events.empty:
            sequences = extract_set_pieces(sp_events)
            sp_df = set_pieces_to_dataframe(sequences)
            efficiency = compute_set_piece_efficiency(sp_df, team_id)
            sp_records = [
                {"Metric": k.replace("_", " ").title(), "Value": v}
                for k, v in efficiency.items()
                if k != "team_id"
            ]
            sp_table = dbc.Table.from_dataframe(
                pd.DataFrame(sp_records),
                striped=True,
                bordered=True,
                size="sm",
            )
        else:
            sp_table = html.P("No set-piece data available.", className="text-muted")

        # --- Transition metrics table ---
        trans_records = []
        for key, metrics in transitions.items():
            label = key.replace("_", " ").title()
            for metric_name, val in metrics.items():
                trans_records.append(
                    {
                        "Category": label,
                        "Metric": metric_name.replace("_", " ").title(),
                        "Value": val,
                    }
                )
        if trans_records:
            trans_table = dbc.Table.from_dataframe(
                pd.DataFrame(trans_records),
                striped=True,
                bordered=True,
                size="sm",
            )
        else:
            trans_table = html.P("No transition data.", className="text-muted")

        status = dbc.Alert(
            f"Scorecard generated — {availability['match_count']} "
            f"matches, {profile.get('total_chains', 0)} possessions.",
            color="success",
            dismissable=True,
        )
        return (kpi_cards, possession_fig, pressing_fig, sp_table, trans_table, status)

    except Exception as e:
        logger.exception("Error generating scorecard")
        error_msg = dbc.Alert([html.Strong("Error: "), str(e)], color="danger")
        return [], empty_fig, empty_fig, "", "", error_msg


# =============================================================================
# ENTRY POINT
# =============================================================================


def main() -> None:
    """Launch the Dash application."""
    from football_analytics.config import config

    app.run(debug=config.dash_debug, port=config.dash_port)


if __name__ == "__main__":
    main()
