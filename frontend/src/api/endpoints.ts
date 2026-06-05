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
    MatchPrediction,
    TeamRatingsResponse,
    CalendarResponse,
    PreMatchPack,
    WeeklyBriefing,
    PlayerAssessmentResult,
    QueryListResponse,
    QueryResult,
    CacheStats,
    SupportedCompetition,
    ExternalFixturesResponse,
    SyncResult,
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

// ─── Prediction Engine ────────────────────────────────────
export const predictMatch = (
    teamAId: number,
    teamBId: number,
    venueType: "home" | "away" | "neutral",
    competitionId?: number,
) =>
    api.post<MatchPrediction>("/predict/match", {
        team_a_id: teamAId,
        team_b_id: teamBId,
        venue_type: venueType,
        competition_id: competitionId,
    });

export const fetchTeamRatings = (competitionId?: number) =>
    api.get<TeamRatingsResponse>("/predict/ratings", {
        competition_id: competitionId,
    });

// ─── Matchday Operations ──────────────────────────────────
export const fetchCalendar = (daysAhead = 14, daysBehind = 7) =>
    api.get<CalendarResponse>("/matchday/calendar", {
        days_ahead: daysAhead,
        days_behind: daysBehind,
    });

export const fetchPreMatchPack = (fixtureId: number) =>
    api.get<PreMatchPack>(`/matchday/fixtures/${fixtureId}/pre-match`);

// ─── External Fixture Sync ────────────────────────────────
export const fetchSupportedCompetitions = () =>
    api.get<{ competitions: SupportedCompetition[] }>("/matchday/competitions");

export const fetchExternalFixtures = (competitionCode: string) =>
    api.get<ExternalFixturesResponse>(`/matchday/external/${competitionCode}`);

export const syncCompetitionFixtures = (competitionCode: string) =>
    api.get<SyncResult>(`/matchday/sync/${competitionCode}`);

// ─── Executive Reporting ──────────────────────────────────
export const fetchWeeklyBriefing = (teamId: number, seasonId?: number) =>
    api.get<WeeklyBriefing>("/executive/weekly-briefing", {
        team_id: teamId,
        season_id: seasonId,
    });

export const fetchPlayerAssessment = (playerId: number, seasonId?: number) =>
    api.post<PlayerAssessmentResult>("/executive/player-assessment", {
        player_id: playerId,
        season_id: seasonId,
    });

// ─── Analysis Workbench ───────────────────────────────────
export const fetchAnalysisQueries = () =>
    api.get<QueryListResponse>("/analysis/queries");

export const executeAnalysisQuery = (queryId: string, parameters: Record<string, unknown>) =>
    api.post<QueryResult>("/analysis/query", {
        query_id: queryId,
        parameters,
    });

// ─── Cache & System ───────────────────────────────────────
export const fetchCacheStats = () => api.get<CacheStats>("/cache/stats");

export const invalidateCache = (name?: string) =>
    api.post<{ invalidated: number }>("/cache/invalidate", { name });
