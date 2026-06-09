import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTeams, fetchSeasons, runSimulation } from "@/api/endpoints";
import { Card, Select, Button, Loading, ErrorState, KPICard, Badge, DisclaimerBanner, HelpPanel } from "@/components/shared";
import { SimulationChart } from "@/components/charts";
import { api } from "@/api";
import type { SimulationResult, TeamRating } from "@/api/types";

type Tab = "simulate" | "ratings" | "tournament";

interface MLPredictionResult {
    home_team: { id: number; name: string };
    away_team: { id: number; name: string };
    probabilities: { home_win: number; draw: number; away_win: number };
    predicted_outcome: string;
    confidence: number;
    expected_goals: { home: number; away: number };
    most_likely_score: string;
    markets: { over_2_5: number; btts: number };
    feature_contributions: Record<string, number>;
    model_version: string;
}

interface TournamentTeamResult {
    team_id: number;
    team_name: string;
    group_name: string;
    group_advance_prob: number;
    round_of_32_prob: number;
    round_of_16_prob: number;
    quarter_final_prob: number;
    semi_final_prob: number;
    final_prob: number;
    winner_prob: number;
    expected_points?: number;
}

export default function SimulationsPage() {
    const [activeTab, setActiveTab] = useState<Tab>("simulate");

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-[var(--text-primary)]">Simulations</h1>
                    <p className="mt-1 text-sm text-[var(--text-muted)]">
                        Match outcome simulation combining Monte Carlo and ML models
                    </p>
                </div>
                <HelpPanel
                    title="Simulations & Predictions"
                    sections={[
                        { heading: "What it does", content: "Runs match outcome simulations using Monte Carlo methods and a trained ML model. Also provides team strength ratings and full tournament simulations." },
                        { heading: "How it works", content: "Monte Carlo runs 10,000 match iterations using team ratings. The ML model uses gradient-boosted features (form, xG history, head-to-head) to predict outcomes. Both models’ results are shown side by side." },
                        { heading: "How to use", content: "In Match Simulation: select two teams and a season, then click Run Simulation. The Ratings tab shows computed team strengths. The Tournament tab lets you simulate entire competitions." },
                    ]}
                />
            </div>

            <DisclaimerBanner />

            <div className="flex gap-2 border-b border-[var(--border-color)] pb-2">
                {(
                    [
                        { id: "simulate", label: "Match Simulation" },
                        { id: "ratings", label: "Team Ratings" },
                        { id: "tournament", label: "Tournament" },
                    ] as const
                ).map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                            activeTab === tab.id
                                ? "bg-accent-500/10 text-accent-500"
                                : "text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]"
                        }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {activeTab === "simulate" && <SimulationTab />}
            {activeTab === "ratings" && <RatingsTab />}
            {activeTab === "tournament" && <TournamentTab />}
        </div>
    );
}

// ─── Unified Simulation Tab ──────────────────────────────────────────────────

function SimulationTab() {
    const [homeTeamId, setHomeTeamId] = useState<number>();
    const [awayTeamId, setAwayTeamId] = useState<number>();
    const [selectedSeasons, setSelectedSeasons] = useState<number[]>([]);
    const [monteCarloResult, setMonteCarloResult] = useState<SimulationResult | null>(null);
    const [mlResult, setMlResult] = useState<MLPredictionResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: fetchTeams });
    const { data: seasons } = useQuery({ queryKey: ["seasons"], queryFn: fetchSeasons });

    const homeTeamName = teams?.find((t) => t.id === homeTeamId)?.name ?? "Home";
    const awayTeamName = teams?.find((t) => t.id === awayTeamId)?.name ?? "Away";

    const handleRunSimulation = async () => {
        if (!homeTeamId || !awayTeamId || selectedSeasons.length === 0) return;
        setLoading(true);
        setError(null);
        setMonteCarloResult(null);
        setMlResult(null);

        const primarySeason = selectedSeasons[selectedSeasons.length - 1];

        try {
            const [mcResult, mlPrediction] = await Promise.allSettled([
                runSimulation(homeTeamId, awayTeamId, primarySeason),
                api.post<MLPredictionResult>("/predict/ml", {
                    home_team_id: homeTeamId,
                    away_team_id: awayTeamId,
                    season_id: primarySeason,
                }),
            ]);

            if (mcResult.status === "fulfilled") setMonteCarloResult(mcResult.value);
            if (mlPrediction.status === "fulfilled") setMlResult(mlPrediction.value);

            if (mcResult.status === "rejected" && mlPrediction.status === "rejected") {
                setError("Both simulation models failed. Check data availability.");
            }
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Simulation failed");
        } finally {
            setLoading(false);
        }
    };

    const toggleSeason = (seasonId: number) => {
        setSelectedSeasons((prev) =>
            prev.includes(seasonId) ? prev.filter((id) => id !== seasonId) : [...prev, seasonId]
        );
    };

    return (
        <div className="space-y-6">
            <Card padding="md">
                <div className="flex flex-wrap items-end gap-4">
                    <Select
                        label="Home Team"
                        options={(teams ?? [])
                            .filter((t) => t.id !== awayTeamId)
                            .map((t) => ({ value: t.id, label: t.name }))}
                        value={homeTeamId}
                        onChange={(v) => setHomeTeamId(Number(v))}
                        placeholder="Select home team..."
                        className="w-full sm:w-52"
                    />
                    <div className="flex items-center pb-2 text-lg font-bold text-[var(--text-muted)]">
                        vs
                    </div>
                    <Select
                        label="Away Team"
                        options={(teams ?? [])
                            .filter((t) => t.id !== homeTeamId)
                            .map((t) => ({ value: t.id, label: t.name }))}
                        value={awayTeamId}
                        onChange={(v) => setAwayTeamId(Number(v))}
                        placeholder="Select away team..."
                        className="w-full sm:w-52"
                    />
                </div>

                <div className="mt-4">
                    <label className="mb-2 block text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
                        Season Context (select one or more)
                    </label>
                    <div className="flex flex-wrap gap-2">
                        {(seasons ?? []).map((s) => (
                            <button
                                key={s.id}
                                onClick={() => toggleSeason(s.id)}
                                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                                    selectedSeasons.includes(s.id)
                                        ? "bg-accent-500 text-white"
                                        : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                                }`}
                            >
                                {s.competition_name} {s.name}
                            </button>
                        ))}
                    </div>
                    {selectedSeasons.length === 0 && (
                        <p className="mt-1 text-xs text-[var(--text-muted)]">Select at least one season</p>
                    )}
                </div>

                <div className="mt-4">
                    <Button
                        onClick={handleRunSimulation}
                        disabled={!homeTeamId || !awayTeamId || selectedSeasons.length === 0 || homeTeamId === awayTeamId || loading}
                        loading={loading}
                    >
                        Run Simulation
                    </Button>
                    {homeTeamId === awayTeamId && homeTeamId !== undefined && (
                        <p className="mt-2 text-xs text-danger-500">Home and away teams must be different</p>
                    )}
                </div>
            </Card>

            {loading && <Loading message="Running simulations (Monte Carlo + ML)..." />}
            {error && <ErrorState message={error} />}

            {(monteCarloResult || mlResult) && (
                <div className="space-y-6 animate-fade-in">
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
                        <KPICard
                            label={`${homeTeamName} Win`}
                            value={`${(((monteCarloResult?.home_win_prob ?? 0) + (mlResult?.probabilities.home_win ?? 0)) / (monteCarloResult && mlResult ? 2 : 1) * 100).toFixed(1)}%`}
                        />
                        <KPICard
                            label="Draw"
                            value={`${(((monteCarloResult?.draw_prob ?? 0) + (mlResult?.probabilities.draw ?? 0)) / (monteCarloResult && mlResult ? 2 : 1) * 100).toFixed(1)}%`}
                        />
                        <KPICard
                            label={`${awayTeamName} Win`}
                            value={`${(((monteCarloResult?.away_win_prob ?? 0) + (mlResult?.probabilities.away_win ?? 0)) / (monteCarloResult && mlResult ? 2 : 1) * 100).toFixed(1)}%`}
                        />
                        <KPICard label="Most Likely Score" value={mlResult?.most_likely_score ?? monteCarloResult?.most_likely_score ?? "—"} />
                        <KPICard label="Over 2.5" value={`${((monteCarloResult?.over_2_5_prob ?? mlResult?.markets.over_2_5 ?? 0) * 100).toFixed(1)}%`} />
                        <KPICard label="BTTS" value={`${((monteCarloResult?.btts_prob ?? mlResult?.markets.btts ?? 0) * 100).toFixed(1)}%`} />
                    </div>

                    {monteCarloResult && mlResult && (
                        <Card title="Model Comparison">
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b border-[var(--border-color)] text-left text-xs text-[var(--text-muted)]">
                                            <th className="pb-2 pr-4">Metric</th>
                                            <th className="pb-2 pr-4">Monte Carlo</th>
                                            <th className="pb-2">ML Model</th>
                                        </tr>
                                    </thead>
                                    <tbody className="text-[var(--text-secondary)]">
                                        <tr className="border-b border-[var(--border-color)]/50">
                                            <td className="py-2 pr-4 font-medium">{homeTeamName} Win</td>
                                            <td className="py-2 pr-4 tabular-nums">{(monteCarloResult.home_win_prob * 100).toFixed(1)}%</td>
                                            <td className="py-2 tabular-nums">{(mlResult.probabilities.home_win * 100).toFixed(1)}%</td>
                                        </tr>
                                        <tr className="border-b border-[var(--border-color)]/50">
                                            <td className="py-2 pr-4 font-medium">Draw</td>
                                            <td className="py-2 pr-4 tabular-nums">{(monteCarloResult.draw_prob * 100).toFixed(1)}%</td>
                                            <td className="py-2 tabular-nums">{(mlResult.probabilities.draw * 100).toFixed(1)}%</td>
                                        </tr>
                                        <tr className="border-b border-[var(--border-color)]/50">
                                            <td className="py-2 pr-4 font-medium">{awayTeamName} Win</td>
                                            <td className="py-2 pr-4 tabular-nums">{(monteCarloResult.away_win_prob * 100).toFixed(1)}%</td>
                                            <td className="py-2 tabular-nums">{(mlResult.probabilities.away_win * 100).toFixed(1)}%</td>
                                        </tr>
                                        <tr>
                                            <td className="py-2 pr-4 font-medium">Expected Goals</td>
                                            <td className="py-2 pr-4 tabular-nums">{monteCarloResult.expected_home_goals.toFixed(2)} — {monteCarloResult.expected_away_goals.toFixed(2)}</td>
                                            <td className="py-2 tabular-nums">{mlResult.expected_goals.home.toFixed(2)} — {mlResult.expected_goals.away.toFixed(2)}</td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </Card>
                    )}

                    {monteCarloResult && (
                        <Card title="Scoreline Distribution" subtitle="Monte Carlo — 10,000 iterations">
                            <SimulationChart result={monteCarloResult} homeTeam={homeTeamName} awayTeam={awayTeamName} />
                        </Card>
                    )}

                    {mlResult && (
                        <Card title="Key Features Driving ML Prediction">
                            <div className="flex items-center gap-2 mb-3">
                                <Badge variant={mlResult.predicted_outcome === "home_win" ? "success" : mlResult.predicted_outcome === "away_win" ? "danger" : "warning"}>
                                    {mlResult.predicted_outcome.replace("_", " ").toUpperCase()}
                                </Badge>
                                <span className="text-xs text-[var(--text-muted)]">
                                    Confidence: {(mlResult.confidence * 100).toFixed(1)}% • Model v{mlResult.model_version}
                                </span>
                            </div>
                            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 max-h-56 overflow-y-auto">
                                {Object.entries(mlResult.feature_contributions)
                                    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
                                    .slice(0, 10)
                                    .map(([feature, value]) => (
                                        <div key={feature} className="flex items-center justify-between text-sm">
                                            <span className="text-[var(--text-secondary)]">{feature.replace(/_/g, " ")}</span>
                                            <span className={`tabular-nums font-medium ${value > 0 ? "text-green-500" : "text-red-500"}`}>
                                                {value > 0 ? "+" : ""}{value.toFixed(3)}
                                            </span>
                                        </div>
                                    ))}
                            </div>
                        </Card>
                    )}
                </div>
            )}
        </div>
    );
}

// ─── Ratings Tab ─────────────────────────────────────────────────────────────

function RatingsTab() {
    const [seasonId, setSeasonId] = useState<number>();
    const [ratings, setRatings] = useState<TeamRating[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const { data: seasons } = useQuery({ queryKey: ["seasons"], queryFn: fetchSeasons });

    const handleFetchRatings = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await api.get<TeamRating[]>("/predict/ratings", { season_id: seasonId });
            setRatings(data || []);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Failed to load ratings");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-4">
            <Card padding="md">
                <p className="mb-3 text-xs text-[var(--text-muted)]">
                    Computed team strength ratings based on offensive, defensive, and form metrics.
                </p>
                <div className="flex items-end gap-4">
                    <Select
                        label="Season"
                        options={(seasons ?? []).map((s) => ({ value: s.id, label: `${s.competition_name} ${s.name}` }))}
                        value={seasonId}
                        onChange={(v) => setSeasonId(Number(v))}
                        placeholder="All seasons"
                        className="w-64"
                    />
                    <Button onClick={handleFetchRatings} disabled={loading} loading={loading}>
                        Load Ratings
                    </Button>
                </div>
            </Card>

            {error && <ErrorState message={error} />}

            {ratings.length > 0 && (
                <Card>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-[var(--border-color)] text-left text-xs text-[var(--text-muted)]">
                                    <th className="pb-2 pr-4">#</th>
                                    <th className="pb-2 pr-4">Team</th>
                                    <th className="pb-2 pr-4">Overall</th>
                                    <th className="pb-2 pr-4">Attack</th>
                                    <th className="pb-2 pr-4">Defence</th>
                                    <th className="pb-2 pr-4">Form</th>
                                    <th className="pb-2">Confidence</th>
                                </tr>
                            </thead>
                            <tbody>
                                {ratings.map((r, i) => (
                                    <tr key={r.team_id} className="border-b border-[var(--border-color)]/50">
                                        <td className="py-2 pr-4 text-[var(--text-muted)]">{i + 1}</td>
                                        <td className="py-2 pr-4 font-medium text-[var(--text-primary)]">{r.team_name}</td>
                                        <td className="py-2 pr-4 tabular-nums">{r.overall_rating.toFixed(2)}</td>
                                        <td className="py-2 pr-4 tabular-nums text-green-500">{r.offensive_strength.toFixed(2)}</td>
                                        <td className="py-2 pr-4 tabular-nums text-blue-500">{r.defensive_strength.toFixed(2)}</td>
                                        <td className="py-2 pr-4">
                                            <span className={`text-xs ${r.form_trend === "improving" ? "text-green-500" : r.form_trend === "declining" ? "text-red-500" : "text-[var(--text-muted)]"}`}>
                                                {r.form_trend === "improving" ? "↑" : r.form_trend === "declining" ? "↓" : "→"} {r.form_trend}
                                            </span>
                                        </td>
                                        <td className="py-2">
                                            <span className="rounded-full bg-[var(--bg-secondary)] px-2 py-0.5 text-xs">{r.confidence}</span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </Card>
            )}
        </div>
    );
}

// ─── Tournament Tab ──────────────────────────────────────────────────────────

interface TournamentSummary {
    id: string;
    name: string;
    year: number;
    host: string;
    total_teams: number;
    num_groups: number;
    status: string;
}

interface TournamentDetail extends TournamentSummary {
    teams_advancing_per_group: number;
    best_third_place_count: number;
    knockout_rounds: number;
    groups: { name: string; teams: string[] }[];
}

// ─── Tournament Bracket Tree ─────────────────────────────────────────────────

interface BracketMatch {
    team1: string;
    team2: string;
    winner: string;
    team1Prob: number;
    team2Prob: number;
}

interface BracketRound {
    name: string;
    matches: BracketMatch[];
}

/**
 * FIFA World Cup bracket paths.
 * Each R16 match is defined by "1X vs 2Y" meaning Winner of Group X vs Runner-up of Group Y.
 * QF/SF/Final are derived by simulating winners through the fixed bracket sides.
 */

// 2018 & 2022: 8 groups (A-H), 16 teams in R16
const FIFA_R16_8_GROUPS: [string, string][] = [
    ["1A", "2B"], // Match 49
    ["1C", "2D"], // Match 50
    ["1E", "2F"], // Match 51
    ["1G", "2H"], // Match 52
    ["1B", "2A"], // Match 53
    ["1D", "2C"], // Match 54
    ["1F", "2E"], // Match 55
    ["1H", "2G"], // Match 56
];

// 2026: 12 groups (A-L), 32 teams (24 from top-2 + 8 best 3rd-place)
// R32 bracket: group winners vs best 3rd-place, runners-up cross-matched
const FIFA_R32_12_GROUPS: [string, string][] = [
    ["1A", "3C/D/E"],  // Match 49
    ["1B", "3A/D/E"],  // Match 50
    ["1C", "3A/B/F"],  // Match 51
    ["1D", "3B/E/F"],  // Match 52
    ["1E", "3C/D/F"],  // Match 53
    ["1F", "3A/B/C"],  // Match 54
    ["1G", "3H/I/J"],  // Match 55
    ["1H", "3G/I/J"],  // Match 56
    ["1I", "3G/H/L"],  // Match 57
    ["1J", "3H/K/L"],  // Match 58
    ["1K", "3I/J/L"],  // Match 59
    ["1L", "3G/K/I"],  // Match 60
    ["2A", "2F"],      // Match 61
    ["2B", "2E"],      // Match 62
    ["2C", "2D"],      // Match 63
    ["2G", "2L"],      // Match 64
    ["2H", "2K"],      // Match 65
    ["2I", "2J"],      // Match 66
];

function getGroupTeams(results: TournamentTeamResult[]) {
    // Group results by group, sorted by group_advance_prob descending within each group
    const groups = new Map<string, TournamentTeamResult[]>();
    for (const r of results) {
        const g = r.group_name;
        if (!groups.has(g)) groups.set(g, []);
        groups.get(g)!.push(r);
    }
    // Sort each group by advancement probability (proxy for group position)
    for (const [, teams] of groups) {
        teams.sort((a, b) => b.group_advance_prob - a.group_advance_prob);
    }
    return groups;
}

function resolveSlot(slot: string, groups: Map<string, TournamentTeamResult[]>, bestThirds: TournamentTeamResult[]): TournamentTeamResult | undefined {
    // "1A" = winner of Group A, "2B" = runner-up of Group B, "3C/D/E" = best 3rd from those groups
    if (slot.startsWith("3")) {
        // Pick the best available 3rd-place team from the specified group options
        const groupOptions = slot.slice(1).split("/");
        const candidate = bestThirds.find(t => {
            const groupLetter = t.group_name.replace("Group ", "");
            return groupOptions.includes(groupLetter);
        });
        return candidate;
    }
    const position = parseInt(slot[0]) - 1; // 0-indexed: "1" = index 0, "2" = index 1
    const groupLetter = slot.slice(1);
    const groupName = `Group ${groupLetter}`;
    const groupTeams = groups.get(groupName);
    return groupTeams?.[position];
}

function deriveBracket(results: TournamentTeamResult[]): BracketRound[] {
    const groups = getGroupTeams(results);
    const numGroups = groups.size;

    // Compute best 3rd-place teams (needed for 2026 format with 12 groups)
    const thirdPlaceTeams: TournamentTeamResult[] = [];
    if (numGroups === 12) {
        for (const [, teams] of groups) {
            if (teams[2]) thirdPlaceTeams.push(teams[2]);
        }
        // Sort by round_of_32_prob (their likelihood to advance beyond groups as 3rd)
        thirdPlaceTeams.sort((a, b) => b.round_of_32_prob - a.round_of_32_prob);
    }

    if (numGroups === 12) {
        // 2026 format: R32 → R16 → QF → SF → Final
        const r32Matches: BracketMatch[] = FIFA_R32_12_GROUPS.map(([slot1, slot2]) => {
            const t1 = resolveSlot(slot1, groups, thirdPlaceTeams);
            const t2 = resolveSlot(slot2, groups, thirdPlaceTeams);
            return {
                team1: t1?.team_name ?? "TBD",
                team2: t2?.team_name ?? "TBD",
                winner: (t1?.round_of_16_prob ?? 0) >= (t2?.round_of_16_prob ?? 0)
                    ? (t1?.team_name ?? "TBD") : (t2?.team_name ?? "TBD"),
                team1Prob: t1?.round_of_32_prob ?? 0,
                team2Prob: t2?.round_of_32_prob ?? 0,
            };
        });

        // R16: winners from R32, paired consecutively (match 49 winner vs match 50 winner, etc.)
        const r16Winners = r32Matches.map(m =>
            results.find(r => r.team_name === m.winner)
        );
        const r16Matches: BracketMatch[] = [];
        for (let i = 0; i < r16Winners.length - 1; i += 2) {
            const t1 = r16Winners[i];
            const t2 = r16Winners[i + 1];
            r16Matches.push({
                team1: t1?.team_name ?? "TBD",
                team2: t2?.team_name ?? "TBD",
                winner: (t1?.quarter_final_prob ?? 0) >= (t2?.quarter_final_prob ?? 0)
                    ? (t1?.team_name ?? "TBD") : (t2?.team_name ?? "TBD"),
                team1Prob: t1?.round_of_16_prob ?? 0,
                team2Prob: t2?.round_of_16_prob ?? 0,
            });
        }

        // QF: winners from R16
        const qfWinners = r16Matches.map(m =>
            results.find(r => r.team_name === m.winner)
        );
        const qfMatches: BracketMatch[] = [];
        for (let i = 0; i < qfWinners.length - 1; i += 2) {
            const t1 = qfWinners[i];
            const t2 = qfWinners[i + 1];
            qfMatches.push({
                team1: t1?.team_name ?? "TBD",
                team2: t2?.team_name ?? "TBD",
                winner: (t1?.semi_final_prob ?? 0) >= (t2?.semi_final_prob ?? 0)
                    ? (t1?.team_name ?? "TBD") : (t2?.team_name ?? "TBD"),
                team1Prob: t1?.quarter_final_prob ?? 0,
                team2Prob: t2?.quarter_final_prob ?? 0,
            });
        }

        // SF: winners from QF
        const sfWinners = qfMatches.map(m =>
            results.find(r => r.team_name === m.winner)
        );
        const sfMatches: BracketMatch[] = [];
        for (let i = 0; i < sfWinners.length - 1; i += 2) {
            const t1 = sfWinners[i];
            const t2 = sfWinners[i + 1];
            sfMatches.push({
                team1: t1?.team_name ?? "TBD",
                team2: t2?.team_name ?? "TBD",
                winner: (t1?.final_prob ?? 0) >= (t2?.final_prob ?? 0)
                    ? (t1?.team_name ?? "TBD") : (t2?.team_name ?? "TBD"),
                team1Prob: t1?.semi_final_prob ?? 0,
                team2Prob: t2?.semi_final_prob ?? 0,
            });
        }

        // Final
        const finalWinners = sfMatches.map(m =>
            results.find(r => r.team_name === m.winner)
        );
        const t1 = finalWinners[0];
        const t2 = finalWinners[1];
        const finalMatch: BracketMatch = {
            team1: t1?.team_name ?? "TBD",
            team2: t2?.team_name ?? "TBD",
            winner: (t1?.winner_prob ?? 0) >= (t2?.winner_prob ?? 0)
                ? (t1?.team_name ?? "TBD") : (t2?.team_name ?? "TBD"),
            team1Prob: t1?.final_prob ?? 0,
            team2Prob: t2?.final_prob ?? 0,
        };

        return [
            { name: "Round of 32", matches: r32Matches },
            { name: "Round of 16", matches: r16Matches },
            { name: "Quarter-Finals", matches: qfMatches },
            { name: "Semi-Finals", matches: sfMatches },
            { name: "Final", matches: [finalMatch] },
        ];
    } else {
        // 2018/2022 format: 8 groups, R16 → QF → SF → Final
        const r16Matches: BracketMatch[] = FIFA_R16_8_GROUPS.map(([slot1, slot2]) => {
            const t1 = resolveSlot(slot1, groups, []);
            const t2 = resolveSlot(slot2, groups, []);
            return {
                team1: t1?.team_name ?? "TBD",
                team2: t2?.team_name ?? "TBD",
                winner: (t1?.quarter_final_prob ?? 0) >= (t2?.quarter_final_prob ?? 0)
                    ? (t1?.team_name ?? "TBD") : (t2?.team_name ?? "TBD"),
                team1Prob: t1?.round_of_16_prob ?? 0,
                team2Prob: t2?.round_of_16_prob ?? 0,
            };
        });

        // QF: R16 winners, consecutive pairs
        const qfWinners = r16Matches.map(m =>
            results.find(r => r.team_name === m.winner)
        );
        const qfMatches: BracketMatch[] = [];
        for (let i = 0; i < qfWinners.length - 1; i += 2) {
            const t1 = qfWinners[i];
            const t2 = qfWinners[i + 1];
            qfMatches.push({
                team1: t1?.team_name ?? "TBD",
                team2: t2?.team_name ?? "TBD",
                winner: (t1?.semi_final_prob ?? 0) >= (t2?.semi_final_prob ?? 0)
                    ? (t1?.team_name ?? "TBD") : (t2?.team_name ?? "TBD"),
                team1Prob: t1?.quarter_final_prob ?? 0,
                team2Prob: t2?.quarter_final_prob ?? 0,
            });
        }

        // SF: QF winners
        const sfWinners = qfMatches.map(m =>
            results.find(r => r.team_name === m.winner)
        );
        const sfMatches: BracketMatch[] = [];
        for (let i = 0; i < sfWinners.length - 1; i += 2) {
            const t1 = sfWinners[i];
            const t2 = sfWinners[i + 1];
            sfMatches.push({
                team1: t1?.team_name ?? "TBD",
                team2: t2?.team_name ?? "TBD",
                winner: (t1?.final_prob ?? 0) >= (t2?.final_prob ?? 0)
                    ? (t1?.team_name ?? "TBD") : (t2?.team_name ?? "TBD"),
                team1Prob: t1?.semi_final_prob ?? 0,
                team2Prob: t2?.semi_final_prob ?? 0,
            });
        }

        // Final
        const finalWinners = sfMatches.map(m =>
            results.find(r => r.team_name === m.winner)
        );
        const ft1 = finalWinners[0];
        const ft2 = finalWinners[1];
        const finalMatch: BracketMatch = {
            team1: ft1?.team_name ?? "TBD",
            team2: ft2?.team_name ?? "TBD",
            winner: (ft1?.winner_prob ?? 0) >= (ft2?.winner_prob ?? 0)
                ? (ft1?.team_name ?? "TBD") : (ft2?.team_name ?? "TBD"),
            team1Prob: ft1?.final_prob ?? 0,
            team2Prob: ft2?.final_prob ?? 0,
        };

        return [
            { name: "Round of 16", matches: r16Matches },
            { name: "Quarter-Finals", matches: qfMatches },
            { name: "Semi-Finals", matches: sfMatches },
            { name: "Final", matches: [finalMatch] },
        ];
    }
}

function BracketMatchCard({ match, compact }: { match: BracketMatch; compact?: boolean }) {
    return (
        <div className={`rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] overflow-hidden ${compact ? "text-xs" : "text-sm"}`}>
            <div className={`flex items-center justify-between px-3 ${compact ? "py-1.5" : "py-2"} ${match.winner === match.team1 ? "bg-accent-500/10 border-l-2 border-l-accent-500" : ""}`}>
                <span className={`${match.winner === match.team1 ? "font-semibold text-[var(--text-primary)]" : "text-[var(--text-muted)]"}`}>
                    {match.team1}
                </span>
                <span className="tabular-nums text-[var(--text-muted)] ml-2">{(match.team1Prob * 100).toFixed(0)}%</span>
            </div>
            <div className="border-t border-[var(--border-color)]" />
            <div className={`flex items-center justify-between px-3 ${compact ? "py-1.5" : "py-2"} ${match.winner === match.team2 ? "bg-accent-500/10 border-l-2 border-l-accent-500" : ""}`}>
                <span className={`${match.winner === match.team2 ? "font-semibold text-[var(--text-primary)]" : "text-[var(--text-muted)]"}`}>
                    {match.team2}
                </span>
                <span className="tabular-nums text-[var(--text-muted)] ml-2">{(match.team2Prob * 100).toFixed(0)}%</span>
            </div>
        </div>
    );
}

function TournamentBracket({ results }: { results: TournamentTeamResult[] }) {
    const rounds = deriveBracket(results);
    const champion = [...results].sort((a, b) => b.winner_prob - a.winner_prob)[0];

    // For display, show only QF onwards to keep the visual manageable
    const displayRounds = rounds.length > 3 ? rounds.slice(-3) : rounds;

    return (
        <div className="space-y-4">
            {/* Champion */}
            <div className="flex flex-col items-center">
                <div className="rounded-xl border-2 border-accent-500 bg-accent-500/10 px-6 py-3 text-center">
                    <div className="text-xs font-medium uppercase tracking-wider text-accent-500 mb-1">🏆 Predicted Champion</div>
                    <div className="text-lg font-bold text-[var(--text-primary)]">{champion.team_name}</div>
                    <div className="text-sm tabular-nums text-accent-500">{(champion.winner_prob * 100).toFixed(1)}% probability</div>
                </div>
            </div>

            {/* Full bracket path - earlier rounds collapsed */}
            {rounds.length > 3 && (
                <details className="group">
                    <summary className="cursor-pointer text-xs font-medium text-accent-500 hover:underline text-center">
                        Show earlier rounds ({rounds.slice(0, -3).map(r => r.name).join(", ")})
                    </summary>
                    <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {rounds.slice(0, -3).map((round) => (
                            <div key={round.name}>
                                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] text-center">
                                    {round.name} ({round.matches.length} matches)
                                </h4>
                                <div className="space-y-1.5 max-h-64 overflow-y-auto">
                                    {round.matches.map((match, i) => (
                                        <BracketMatchCard key={i} match={match} compact />
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </details>
            )}

            {/* QF / SF / Final displayed prominently */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {displayRounds.map((round) => (
                    <div key={round.name}>
                        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] text-center">
                            {round.name}
                        </h4>
                        <div className="space-y-2">
                            {round.matches.map((match, i) => (
                                <BracketMatchCard key={i} match={match} compact={round.matches.length > 2} />
                            ))}
                        </div>
                    </div>
                ))}
            </div>

            <p className="text-center text-xs text-[var(--text-muted)]">
                Bracket follows official FIFA knockout draw structure. Predicted winners determined by stage advancement probabilities.
            </p>
        </div>
    );
}

function TournamentTab() {
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [nSimulations, setNSimulations] = useState(10000);
    const [results, setResults] = useState<TournamentTeamResult[] | null>(null);
    const [tournamentName, setTournamentName] = useState<string>("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const { data: tournaments, isLoading: tournamentsLoading } = useQuery({
        queryKey: ["tournaments"],
        queryFn: () => api.get<TournamentSummary[]>("/predict/tournaments"),
    });

    const { data: detail } = useQuery({
        queryKey: ["tournament-detail", selectedId],
        queryFn: () => api.get<TournamentDetail>(`/predict/tournaments/${selectedId}`),
        enabled: !!selectedId,
    });

    const handleSimulate = async () => {
        if (!selectedId) return;
        setLoading(true);
        setError(null);
        setResults(null);
        try {
            const data = await api.post<{ tournament_name: string; team_results: TournamentTeamResult[] }>("/predict/tournament", {
                tournament_id: selectedId,
                n_simulations: nSimulations,
            });
            setResults(data.team_results || []);
            setTournamentName(data.tournament_name || "");
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Tournament simulation failed");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-4">
            {/* Tournament Selection */}
            <Card padding="md">
                <p className="mb-3 text-xs text-[var(--text-muted)]">
                    Select a FIFA World Cup tournament and simulate the full competition using Monte Carlo methods.
                </p>

                {tournamentsLoading ? (
                    <Loading message="Loading tournaments..." />
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                        {(tournaments ?? []).map((t) => (
                            <button
                                key={t.id}
                                onClick={() => { setSelectedId(t.id); setResults(null); }}
                                className={`relative rounded-xl border p-4 text-left transition-all ${
                                    selectedId === t.id
                                        ? "border-accent-500 bg-accent-500/10 ring-1 ring-accent-500/30"
                                        : "border-[var(--border-color)] bg-[var(--bg-secondary)] hover:border-accent-500/50"
                                }`}
                            >
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-lg font-bold text-[var(--text-primary)]">{t.year}</span>
                                    <Badge variant={t.status === "upcoming" ? "info" : "default"}>{t.status}</Badge>
                                </div>
                                <p className="text-xs text-[var(--text-muted)]">{t.host}</p>
                                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                                    {t.total_teams} teams · {t.num_groups} groups
                                </p>
                            </button>
                        ))}
                    </div>
                )}

                {selectedId && (
                    <div className="flex items-end gap-4">
                        <div>
                            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">Simulations</label>
                            <input
                                type="number"
                                value={nSimulations}
                                onChange={(e) => setNSimulations(Number(e.target.value) || 10000)}
                                min={100}
                                max={50000}
                                className="w-28 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-sm"
                            />
                        </div>
                        <Button onClick={handleSimulate} disabled={loading} loading={loading}>
                            Simulate Tournament
                        </Button>
                    </div>
                )}
            </Card>

            {/* Group Stage Overview */}
            {detail && !results && (
                <Card title={`${detail.name} — Groups`}>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                        {detail.groups.map((g) => (
                            <div key={g.name} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
                                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-accent-500">{g.name}</h4>
                                <ul className="space-y-1">
                                    {g.teams.map((team) => (
                                        <li key={team} className="text-sm text-[var(--text-primary)]">{team}</li>
                                    ))}
                                </ul>
                            </div>
                        ))}
                    </div>
                    <p className="mt-3 text-xs text-[var(--text-muted)]">
                        Top {detail.teams_advancing_per_group} per group advance
                        {detail.best_third_place_count > 0 && ` + ${detail.best_third_place_count} best third-placed teams`}
                        {" → "}{detail.knockout_rounds} knockout rounds
                    </p>
                </Card>
            )}

            {error && <ErrorState message={error} />}

            {/* Tournament Bracket Tree */}
            {results && results.length > 0 && (
                <Card title={`${tournamentName} — Predicted Bracket`}>
                    <TournamentBracket results={results} />
                </Card>
            )}

            {/* Results Table */}
            {results && results.length > 0 && (
                <Card title={`${tournamentName} — Simulation Results`}>
                    <p className="mb-3 text-xs text-[var(--text-muted)]">
                        Based on {nSimulations.toLocaleString()} Monte Carlo simulations. Probabilities reflect each team's chance of reaching each stage.
                    </p>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-[var(--border-color)] text-left text-xs text-[var(--text-muted)]">
                                    <th className="pb-2 pr-3">#</th>
                                    <th className="pb-2 pr-3">Team</th>
                                    <th className="pb-2 pr-3">Group</th>
                                    <th className="pb-2 pr-3">Advance %</th>
                                    <th className="pb-2 pr-3">QF %</th>
                                    <th className="pb-2 pr-3">SF %</th>
                                    <th className="pb-2 pr-3">Final %</th>
                                    <th className="pb-2">Winner %</th>
                                </tr>
                            </thead>
                            <tbody>
                                {results.map((r, i) => (
                                    <tr key={r.team_id} className="border-b border-[var(--border-color)]/50">
                                        <td className="py-2 pr-3 text-[var(--text-muted)]">{i + 1}</td>
                                        <td className="py-2 pr-3 font-medium text-[var(--text-primary)]">{r.team_name}</td>
                                        <td className="py-2 pr-3 text-xs text-[var(--text-muted)]">{r.group_name}</td>
                                        <td className="py-2 pr-3 tabular-nums">{(r.group_advance_prob * 100).toFixed(1)}%</td>
                                        <td className="py-2 pr-3 tabular-nums">{(r.quarter_final_prob * 100).toFixed(1)}%</td>
                                        <td className="py-2 pr-3 tabular-nums">{(r.semi_final_prob * 100).toFixed(1)}%</td>
                                        <td className="py-2 pr-3 tabular-nums">{(r.final_prob * 100).toFixed(1)}%</td>
                                        <td className="py-2 tabular-nums font-semibold text-accent-500">{(r.winner_prob * 100).toFixed(1)}%</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </Card>
            )}
        </div>
    );
}
