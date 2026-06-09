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
    winner_prob: number;
    final_prob: number;
    semi_final_prob: number;
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

function TournamentTab() {
    const [format, setFormat] = useState<"league" | "groups_knockout" | "knockout">("league");
    const [selectedTeams, setSelectedTeams] = useState<number[]>([]);
    const [nSimulations, setNSimulations] = useState(1000);
    const [results, setResults] = useState<TournamentTeamResult[] | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: fetchTeams });

    const toggleTeam = (teamId: number) => {
        setSelectedTeams((prev) => prev.includes(teamId) ? prev.filter((id) => id !== teamId) : [...prev, teamId]);
    };

    const handleSimulate = async () => {
        if (selectedTeams.length < 2) return;
        setLoading(true);
        setError(null);
        try {
            const data = await api.post<{ team_results: TournamentTeamResult[] }>("/predict/tournament", {
                format_type: format,
                team_ids: selectedTeams,
                n_simulations: nSimulations,
            });
            setResults(data.team_results || []);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Tournament simulation failed");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-4">
            <Card padding="md">
                <p className="mb-3 text-xs text-[var(--text-muted)]">
                    Simulate an entire competition — league, group stage + knockout, or straight knockout.
                </p>
                <div className="flex flex-wrap items-end gap-4 mb-4">
                    <Select
                        label="Format"
                        options={[
                            { value: "league", label: "League (Round Robin)" },
                            { value: "groups_knockout", label: "Groups + Knockout" },
                            { value: "knockout", label: "Knockout" },
                        ]}
                        value={format}
                        onChange={(v) => setFormat(v as typeof format)}
                        className="w-56"
                    />
                    <div>
                        <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">Simulations</label>
                        <input
                            type="number"
                            value={nSimulations}
                            onChange={(e) => setNSimulations(Number(e.target.value) || 1000)}
                            min={100}
                            max={50000}
                            className="w-28 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-sm"
                        />
                    </div>
                </div>

                <label className="mb-2 block text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
                    Teams ({selectedTeams.length} selected)
                </label>
                <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
                    {(teams ?? []).map((t) => (
                        <button
                            key={t.id}
                            onClick={() => toggleTeam(t.id)}
                            className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                                selectedTeams.includes(t.id)
                                    ? "bg-accent-500 text-white"
                                    : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                            }`}
                        >
                            {t.name}
                        </button>
                    ))}
                </div>

                <div className="mt-4">
                    <Button onClick={handleSimulate} disabled={selectedTeams.length < 2 || loading} loading={loading}>
                        Simulate Tournament
                    </Button>
                </div>
            </Card>

            {error && <ErrorState message={error} />}

            {results && results.length > 0 && (
                <Card title="Tournament Projection">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-[var(--border-color)] text-left text-xs text-[var(--text-muted)]">
                                    <th className="pb-2 pr-4">#</th>
                                    <th className="pb-2 pr-4">Team</th>
                                    <th className="pb-2 pr-4">Win %</th>
                                    <th className="pb-2 pr-4">Final %</th>
                                    <th className="pb-2 pr-4">Semi %</th>
                                    {format === "league" && <th className="pb-2">Exp. Pts</th>}
                                </tr>
                            </thead>
                            <tbody>
                                {results.sort((a, b) => b.winner_prob - a.winner_prob).map((r, i) => (
                                    <tr key={r.team_id} className="border-b border-[var(--border-color)]/50">
                                        <td className="py-2 pr-4 text-[var(--text-muted)]">{i + 1}</td>
                                        <td className="py-2 pr-4 font-medium text-[var(--text-primary)]">{r.team_name}</td>
                                        <td className="py-2 pr-4 tabular-nums font-semibold text-accent-500">{(r.winner_prob * 100).toFixed(1)}%</td>
                                        <td className="py-2 pr-4 tabular-nums">{(r.final_prob * 100).toFixed(1)}%</td>
                                        <td className="py-2 pr-4 tabular-nums">{(r.semi_final_prob * 100).toFixed(1)}%</td>
                                        {format === "league" && <td className="py-2 tabular-nums">{r.expected_points?.toFixed(1) ?? "—"}</td>}
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
