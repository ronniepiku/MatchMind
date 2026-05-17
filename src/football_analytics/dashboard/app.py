"""Interactive Football Analytics Dashboard — Plotly Dash.

Two main views:
1. Opponent Profile — Pre-match scouting report with attack patterns,
   defensive shape, and key player threats.
2. Player Performance — Individual player metrics, rolling form, and
   radar comparison charts.

Run: `uv run fb-dashboard` or `uv run python -m football_analytics.dashboard.app`
"""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from football_analytics.analysis.opponent_profile import build_opponent_report
from football_analytics.analysis.player_performance import (
    get_player_rolling_form,
    get_player_season_summary,
    get_squad_comparison,
)
from football_analytics.db import get_engine

# =============================================================================
# APP INITIALISATION
# =============================================================================

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True,
    title="Football Analytics Dashboard",
)

# =============================================================================
# LAYOUT
# =============================================================================

# Navigation bar
navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Opponent Profile", href="/opponent")),
        dbc.NavItem(dbc.NavLink("Player Performance", href="/player")),
    ],
    brand="Football Analytics",
    brand_href="/",
    color="primary",
    dark=True,
)

# Page content container
app.layout = dbc.Container([
    dcc.Location(id="url", refresh=False),
    navbar,
    html.Br(),
    html.Div(id="page-content"),
], fluid=True)


# =============================================================================
# PAGE: OPPONENT PROFILE
# =============================================================================

opponent_layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H2("Opponent Scouting Report"),
            html.Hr(),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Team ID"),
                    dbc.Input(id="opponent-team-id", type="number", value=771, placeholder="Team ID"),
                ], md=4),
                dbc.Col([
                    dbc.Label("Season ID"),
                    dbc.Input(id="opponent-season-id", type="number", value=106, placeholder="Season ID"),
                ], md=4),
                dbc.Col([
                    dbc.Button("Generate Report", id="btn-opponent-report", color="primary", className="mt-4"),
                ], md=4),
            ]),
        ]),
    ]),
    html.Br(),
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Attack Patterns"),
                dbc.CardBody(id="opponent-attack-table"),
            ]),
        ], md=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Defensive Shape by Zone"),
                dbc.CardBody(id="opponent-defense-chart"),
            ]),
        ], md=6),
    ]),
    html.Br(),
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Key Players (by xG + xA)"),
                dbc.CardBody(id="opponent-key-players"),
            ]),
        ]),
    ]),
])


# =============================================================================
# PAGE: PLAYER PERFORMANCE
# =============================================================================

player_layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H2("Player Performance Dashboard"),
            html.Hr(),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Player ID"),
                    dbc.Input(id="player-id", type="number", value=5503, placeholder="Player ID"),
                ], md=3),
                dbc.Col([
                    dbc.Label("Team ID"),
                    dbc.Input(id="player-team-id", type="number", value=771, placeholder="Team ID"),
                ], md=3),
                dbc.Col([
                    dbc.Label("Season ID"),
                    dbc.Input(id="player-season-id", type="number", value=106, placeholder="Season ID"),
                ], md=3),
                dbc.Col([
                    dbc.Button("Analyse", id="btn-player-analyse", color="primary", className="mt-4"),
                ], md=3),
            ]),
        ]),
    ]),
    html.Br(),
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Season Summary"),
                dbc.CardBody(id="player-summary-table"),
            ]),
        ], md=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Rolling Form (xG)"),
                dbc.CardBody(dcc.Graph(id="player-rolling-chart")),
            ]),
        ], md=6),
    ]),
    html.Br(),
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Squad Comparison"),
                dbc.CardBody(id="squad-comparison-table"),
            ]),
        ]),
    ]),
])


# =============================================================================
# HOME PAGE
# =============================================================================

home_layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Football Analytics Platform", className="text-center mt-4"),
            html.P(
                "StatsBomb open-data powered analysis for coaches, analysts, and scouts.",
                className="text-center text-muted",
            ),
            html.Hr(),
            dbc.Row([
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H4("Opponent Profile"),
                        html.P("Pre-match scouting: attack patterns, defensive shape, key threats."),
                        dbc.Button("Open", href="/opponent", color="primary"),
                    ]),
                ]), md=6),
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H4("Player Performance"),
                        html.P("Individual metrics, rolling form, and radar comparisons."),
                        dbc.Button("Open", href="/player", color="primary"),
                    ]),
                ]), md=6),
            ]),
        ]),
    ]),
])


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
    return home_layout


# =============================================================================
# CALLBACKS: OPPONENT PROFILE
# =============================================================================

@callback(
    [
        Output("opponent-attack-table", "children"),
        Output("opponent-defense-chart", "children"),
        Output("opponent-key-players", "children"),
    ],
    Input("btn-opponent-report", "n_clicks"),
    [
        dash.State("opponent-team-id", "value"),
        dash.State("opponent-season-id", "value"),
    ],
    prevent_initial_call=True,
)
def update_opponent_report(
    n_clicks: int | None,
    team_id: int,
    season_id: int,
) -> tuple:
    """Generate opponent scouting report on button click."""
    if not team_id or not season_id:
        return "Enter valid IDs", "", ""

    try:
        engine = get_engine()
        report = build_opponent_report(team_id, season_id, engine)

        # Attack patterns table
        attack_table = dbc.Table.from_dataframe(
            report["attack_patterns"], striped=True, bordered=True, hover=True, size="sm"
        ) if not report["attack_patterns"].empty else html.P("No data available")

        # Defensive shape bar chart
        if not report["defensive_shape"].empty:
            defense_fig = px.bar(
                report["defensive_shape"],
                x="zone",
                y=["pressures", "tackles", "interceptions"],
                barmode="group",
                title="Defensive Actions by Zone",
                template="plotly_white",
            )
            defense_chart = dcc.Graph(figure=defense_fig)
        else:
            defense_chart = html.P("No data available")

        # Key players table
        key_players_table = dbc.Table.from_dataframe(
            report["key_players"], striped=True, bordered=True, hover=True, size="sm"
        ) if not report["key_players"].empty else html.P("No data available")

        return attack_table, defense_chart, key_players_table

    except Exception as e:
        error_msg = html.P(f"Error: {e}", className="text-danger")
        return error_msg, error_msg, error_msg


# =============================================================================
# CALLBACKS: PLAYER PERFORMANCE
# =============================================================================

@callback(
    [
        Output("player-summary-table", "children"),
        Output("player-rolling-chart", "figure"),
        Output("squad-comparison-table", "children"),
    ],
    Input("btn-player-analyse", "n_clicks"),
    [
        dash.State("player-id", "value"),
        dash.State("player-team-id", "value"),
        dash.State("player-season-id", "value"),
    ],
    prevent_initial_call=True,
)
def update_player_performance(
    n_clicks: int | None,
    player_id: int,
    team_id: int,
    season_id: int,
) -> tuple:
    """Generate player performance analysis on button click."""
    empty_fig = go.Figure()

    if not player_id or not season_id:
        return "Enter valid IDs", empty_fig, ""

    try:
        engine = get_engine()

        # Season summary
        summary = get_player_season_summary(engine, player_id, season_id)
        summary_table = dbc.Table.from_dataframe(
            summary.T.reset_index().rename(columns={"index": "Metric", 0: "Value"}),
            striped=True, bordered=True, size="sm",
        ) if not summary.empty else html.P("No data")

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
            )
        else:
            rolling_fig = empty_fig

        # Squad comparison
        squad = get_squad_comparison(engine, team_id, season_id)
        squad_table = dbc.Table.from_dataframe(
            squad, striped=True, bordered=True, hover=True, size="sm"
        ) if not squad.empty else html.P("No data")

        return summary_table, rolling_fig, squad_table

    except Exception as e:
        return html.P(f"Error: {e}", className="text-danger"), empty_fig, ""


# =============================================================================
# ENTRY POINT
# =============================================================================


def main() -> None:
    """Launch the Dash application."""
    from football_analytics.config import config
    app.run(debug=config.dash_debug, port=config.dash_port)


if __name__ == "__main__":
    main()
