// ─── Common ───────────────────────────────────────────────
export interface Team {
    id: number;
    name: string;
    short_name?: string;
}

export interface Season {
    id: number;
    name: string;
    competition_name: string;
}

export interface Player {
    id: number;
    name: string;
    position: string;
    team_id: number;
}

export interface Match {
    id: number;
    home_team: string;
    away_team: string;
    home_score: number;
    away_score: number;
    date: string;
    competition: string;
}

// ─── Opponent Profile ─────────────────────────────────────
export interface AttackPattern {
    pattern_type: string;
    frequency: number;
    success_rate: number;
    xg_per_attack: number;
}

export interface DefensiveShape {
    zone: string;
    tackles: number;
    interceptions: number;
    pressures: number;
    recoveries: number;
}

export interface KeyPlayer {
    player_name: string;
    position: string;
    goals: number;
    assists: number;
    xg: number;
    xa: number;
    minutes: number;
    threat_rating: number;
}

export interface OpponentReport {
    team_name: string;
    attack_patterns: AttackPattern[];
    defensive_shape: DefensiveShape[];
    key_players: KeyPlayer[];
}

// ─── Player Performance ───────────────────────────────────
export interface PlayerSeasonSummary {
    matches_played: number;
    minutes: number;
    goals: number;
    assists: number;
    xg: number;
    xa: number;
    xg_per_90: number;
    xa_per_90: number;
    passes_completed: number;
    pass_accuracy: number;
    tackles_won: number;
    interceptions: number;
    pressures: number;
}

export interface RollingFormDataPoint {
    match_date: string;
    match_label: string;
    xg: number;
    xa: number;
    xg_rolling: number;
    xa_rolling: number;
}

export interface RadarMetric {
    metric: string;
    value: number;
    percentile: number;
}

export interface SquadComparisonPlayer {
    player_name: string;
    position: string;
    minutes: number;
    goals: number;
    assists: number;
    xg_per_90: number;
    xa_per_90: number;
    rating: number;
}

// ─── Team Scorecard ───────────────────────────────────────
export interface TeamKPI {
    label: string;
    value: number;
    change?: number;
    unit?: string;
}

export interface PossessionProfile {
    name: string;
    percentage: number;
}

export interface TransitionMetric {
    metric: string;
    value: number;
    league_avg: number;
    percentile: number;
}

export interface SetPieceEfficiency {
    type: string;
    total: number;
    chances_created: number;
    goals: number;
    xg: number;
    conversion_rate: number;
}

export interface TeamScorecard {
    kpis: TeamKPI[];
    possession_profile: PossessionProfile[];
    pressing_intensity: { zone: string; pressures_per_90: number }[];
    transitions: TransitionMetric[];
    set_pieces: SetPieceEfficiency[];
}

// ─── Match Analysis ───────────────────────────────────────
export interface ShotEvent {
    x: number;
    y: number;
    xg: number;
    outcome: "goal" | "saved" | "blocked" | "off_target" | "post";
    player_name: string;
    minute: number;
    team: string;
    body_part: string;
    technique: string;
}

export interface PassNetworkNode {
    player_name: string;
    position: string;
    x: number;
    y: number;
    passes_made: number;
}

export interface PassNetworkEdge {
    source: string;
    target: string;
    passes: number;
    progressive: number;
}

export interface PassingNetwork {
    nodes: PassNetworkNode[];
    edges: PassNetworkEdge[];
}

export interface XgTimelineEvent {
    minute: number;
    team: string;
    xg: number;
    cumulative_xg: number;
    player_name: string;
    outcome: string;
}

export interface PressureEvent {
    x: number;
    y: number;
    success: boolean;
    minute: number;
    player_name: string;
}

// ─── Match Simulation ─────────────────────────────────────
export interface SimulationResult {
    home_win_prob: number;
    draw_prob: number;
    away_win_prob: number;
    expected_home_goals: number;
    expected_away_goals: number;
    most_likely_score: string;
    over_2_5_prob: number;
    btts_prob: number;
    scoreline_distribution: { score: string; probability: number }[];
}

// ─── Player Similarity ────────────────────────────────────
export interface SimilarPlayer {
    player_name: string;
    team: string;
    position: string;
    similarity_score: number;
    age: number;
    minutes: number;
    key_metrics: Record<string, number>;
}

// ─── API Responses ────────────────────────────────────────
export interface DataAvailability {
    matches: number;
    has_data: boolean;
}

// ─── Prediction Engine ────────────────────────────────────
export interface MatchPrediction {
    team_a_win_prob: number;
    draw_prob: number;
    team_b_win_prob: number;
    most_likely_score: [number, number];
    confidence: string;
    team_a_expected_xg: number;
    team_b_expected_xg: number;
    key_factors: string[];
    n_simulations: number;
}

export interface TeamRating {
    team_id: number;
    team_name: string;
    overall_rating: number;
    offensive_strength: number;
    defensive_strength: number;
    form_trend: string;
    confidence: string;
    rating_date: string;
}

export interface TeamRatingsResponse {
    ratings: TeamRating[];
    model_version: string;
}

// ─── Matchday Operations ──────────────────────────────────
export interface Fixture {
    fixture_id: number;
    match_date: string | null;
    competition_name: string;
    home_team: { id: number; name: string };
    away_team: { id: number; name: string };
    venue_type: string;
    stage: string;
    status: string;
    days_until: number | null;
    priority: number;
}

export interface CalendarResponse {
    upcoming_count: number;
    needing_preview: number;
    needing_review: number;
    upcoming_fixtures: Fixture[];
    recent_results: Fixture[];
    status_counts: Record<string, number>;
}

export interface PreMatchPack {
    fixture_id: number;
    opponent_profile: Record<string, unknown>;
    prediction: MatchPrediction;
    tactical_suggestions: string[];
    key_threats: string[];
}

// ─── Executive Reporting ──────────────────────────────────
export interface RAGMetric {
    name: string;
    value: number | string;
    unit: string;
    rag: "red" | "amber" | "green";
    trend: "improving" | "stable" | "declining";
    context: string;
}

export interface WeeklyBriefing {
    reporting_period: string;
    headline: string;
    key_points: string[];
    recommendations: string[];
    squad_metrics: RAGMetric[];
    week_difficulty: "red" | "amber" | "green";
}

export interface PlayerAssessmentResult {
    player_name: string;
    position: string;
    kpis: RAGMetric[];
    trajectory: string;
    recommendation: string;
    rationale: string[];
}

// ─── Analysis Workbench ───────────────────────────────────
export interface QueryParameter {
    name: string;
    type: string;
    description: string;
    required: boolean;
    default: unknown;
}

export interface QueryDefinition {
    query_id: string;
    name: string;
    description: string;
    category: string;
    parameters: QueryParameter[];
}

export interface QueryListResponse {
    queries: QueryDefinition[];
    categories: string[];
}

export interface QueryResult {
    query_id: string;
    parameters: Record<string, unknown>;
    row_count: number;
    results: Record<string, unknown>[];
}

// ─── Cache & System ───────────────────────────────────────
export interface CacheStats {
    files: number;
    total_size_mb: number;
    oldest_seconds_ago: number | null;
    newest_seconds_ago: number | null;
}

// ─── External Fixtures ────────────────────────────────────
export interface SupportedCompetition {
    code: string;
    name: string;
    id: number;
}

export interface ExternalFixture {
    external_id: number;
    match_date: string | null;
    kick_off: string | null;
    home_team: { id: number; name: string };
    away_team: { id: number; name: string };
    matchday: number;
    stage: string;
    status: string;
    competition_name: string;
}

export interface ExternalFixturesResponse {
    competition: string;
    code: string;
    count: number;
    fixtures: ExternalFixture[];
}

export interface SyncResult {
    competition: string;
    code: string;
    created: number;
    skipped: number;
    total: number;
}
