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
    style: string;
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
