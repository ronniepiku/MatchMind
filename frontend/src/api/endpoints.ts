import api from "./client";
import type {
    Team,
    Season,
    Player,
    Match,
    OpponentReport,
    PlayerSeasonSummary,
    RollingFormDataPoint,
    RadarMetric,
    SquadComparisonPlayer,
    TeamScorecard,
    ShotEvent,
    PassingNetwork,
    XgTimelineEvent,
    PressureEvent,
    SimulationResult,
    SimilarPlayer,
    DataAvailability,
} from "./types";

// ─── Reference Data ───────────────────────────────────────
export const fetchTeams = () => api.get<Team[]>("/teams");

export const fetchSeasons = () => api.get<Season[]>("/seasons");

export const fetchPlayers = (teamId: number, seasonId: number) =>
    api.get<Player[]>("/players", { team_id: teamId, season_id: seasonId });

export const fetchMatches = (teamId: number, seasonId: number) =>
    api.get<Match[]>("/matches", { team_id: teamId, season_id: seasonId });

export const checkDataAvailability = (teamId: number, seasonId: number) =>
    api.get<DataAvailability>("/data-availability", {
        team_id: teamId,
        season_id: seasonId,
    });

// ─── Opponent Profile ─────────────────────────────────────
export const fetchOpponentReport = (teamId: number, seasonId: number) =>
    api.get<OpponentReport>("/opponent/report", {
        team_id: teamId,
        season_id: seasonId,
    });

// ─── Player Performance ───────────────────────────────────
export const fetchPlayerSummary = (playerId: number, seasonId: number) =>
    api.get<PlayerSeasonSummary>("/player/summary", {
        player_id: playerId,
        season_id: seasonId,
    });

export const fetchPlayerRollingForm = (playerId: number, seasonId: number) =>
    api.get<RollingFormDataPoint[]>("/player/rolling-form", {
        player_id: playerId,
        season_id: seasonId,
    });

export const fetchPlayerRadar = (playerId: number, seasonId: number) =>
    api.get<RadarMetric[]>("/player/radar", {
        player_id: playerId,
        season_id: seasonId,
    });

export const fetchSquadComparison = (teamId: number, seasonId: number) =>
    api.get<SquadComparisonPlayer[]>("/player/squad-comparison", {
        team_id: teamId,
        season_id: seasonId,
    });

// ─── Team Scorecard ───────────────────────────────────────
export const fetchTeamScorecard = (teamId: number, seasonId: number) =>
    api.get<TeamScorecard>("/team/scorecard", {
        team_id: teamId,
        season_id: seasonId,
    });

// ─── Match Analysis ───────────────────────────────────────
export const fetchShotMap = (matchId: number) =>
    api.get<ShotEvent[]>("/match/shots", { match_id: matchId });

export const fetchPassingNetwork = (matchId: number, teamId: number) =>
    api.get<PassingNetwork>("/match/passing-network", {
        match_id: matchId,
        team_id: teamId,
    });

export const fetchXgTimeline = (matchId: number) =>
    api.get<XgTimelineEvent[]>("/match/xg-timeline", { match_id: matchId });

export const fetchPressureMap = (matchId: number, teamId: number) =>
    api.get<PressureEvent[]>("/match/pressure-map", {
        match_id: matchId,
        team_id: teamId,
    });

// ─── Simulation ───────────────────────────────────────────
export const runSimulation = (homeTeamId: number, awayTeamId: number, seasonId: number) =>
    api.post<SimulationResult>("/simulation/match", {
        home_team_id: homeTeamId,
        away_team_id: awayTeamId,
        season_id: seasonId,
    });

// ─── Player Similarity ────────────────────────────────────
export const fetchSimilarPlayers = (playerId: number, topN?: number, seasonId?: number) =>
    api.get<SimilarPlayer[]>("/player/similar", {
        player_id: playerId,
        top_n: topN ?? 10,
        season_id: seasonId,
    });
