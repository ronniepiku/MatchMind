import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
    fetchTeams,
    fetchSeasons,
    runSimulation,
} from "@/api/endpoints";
import { Card, Select, Button, Loading, ErrorState, KPICard, Badge } from "@/components/shared";
import { SimulationChart } from "@/components/charts";
import { api } from "@/api";
import type { TeamRating } from "@/api/types";

type Tab = "simulate" | "ml-predict" | "ratings" | "tournament";

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

interface MLModelStatus {
    model_available: boolean;
    model_version: string;
    metrics: {
        brier_score: number;
        log_loss: number;
        accuracy: number;
        n_matches: number;
    } | null;
}

export default function PredictionsHub() {
    const [activeTab, setActiveTab] = useState<Tab>("simulate");

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                    Predictions & Simulation
                </h1>
                <p className="mt-1 text-sm text-[var(--text-muted)]">
                    Match outcome forecasting, Monte Carlo simulation, team ratings, and ML predictions
                </p>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-2 border-b border-[var(--border-color)] pb-2">
                {(
                    [
                        { id: "simulate", label: "Match Simulation" },
                        { id: "ml-predict", label: "ML Prediction" },
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
            {activeTab === "ml-predict" && <MLPredictionTab />}
            {activeTab === "ratings" && <RatingsTab />}
            {activeTab === "tournament" && <TournamentTab />}
        </div>
    );
}

// ─── Simulation Tab ──────────────────────────────────────────────────────────

function SimulationTab() {
    const [homeTeamId, setHomeTeamId] = useState<number>();
    const [awayTeamId, setAwayTeamId] = useState<number>();
    const [seasonId, setSeasonId] = useState<number>();
    const [shouldRun, setShouldRun] = useState(false);

    const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: fetchTeams });
    const { data: seasons } = useQuery({ queryKey: ["seasons"], queryFn: fetchSeasons });

    const {
        data: result,
        isLoading,
        error,
        refetch,
    } = useQuery({
        queryKey: ["simulation", homeTeamId, awayTeamId, seasonId],
        queryFn: () => runSimulation(homeTeamId!, awayTeamId!, seasonId!),
        enabled: shouldRun && !!homeTeamId && !!awayTeamId && !!seasonId,
    });

    const handleRun = () => {
        setShouldRun(true);
        if (shouldRun) refetch();
    };

    const homeTeamName = teams?.find((t) => t.id === homeTeamId)?.name ?? "Home";
    const awayTeamName = teams?.find((t) => t.id === awayTeamId)?.name ?? "Away";

    return (
        <div className="space-y-6">
            <Card padding="md">
                <p className="mb-4 text-xs text-[var(--text-muted)]">
                    Monte Carlo simulation — 10,000 iterations using Poisson-based match model
                </p>
                <div className="flex flex-wrap items-end gap-4">
                    <Select
                        label="Home Team"
                        options={(teams ?? [])
                            .filter((t) => t.id !== awayTeamId)
                            .map((t) => ({ value: t.id, label: t.name }))}
                        value={homeTeamId}
                        onChange={(v) => {
                            setHomeTeamId(Number(v));
                            setShouldRun(false);
                        }}
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
                        onChange={(v) => {
                            setAwayTeamId(Number(v));
                            setShouldRun(false);
                        }}
                        placeholder="Select away team..."
                        className="w-full sm:w-52"
                    />
                    <Select
                        label="Season"
                        options={(seasons ?? []).map((s) => ({
                            value: s.id,
                            label: `${s.competition_name} ${s.name}`,
                        }))}
                        value={seasonId}
                        onChange={(v) => {
                            setSeasonId(Number(v));
                            setShouldRun(false);
                        }}
                        placeholder="Select season..."
                        className="w-full sm:w-56"
                    />
                    <Button
                        onClick={handleRun}
                        disabled={!homeTeamId || !awayTeamId || !seasonId || homeTeamId === awayTeamId}
                        loading={isLoading}
                    >
                        Run Simulation
                    </Button>
                </div>
                {homeTeamId === awayTeamId && homeTeamId !== undefined && (
                    <p className="mt-2 text-xs text-danger-500">
                        Home and away teams must be different
                    </p>
                )}
            </Card>

            {isLoading && <Loading message="Running Monte Carlo simulation (10,000 iterations)..." />}
            {error && <ErrorState onRetry={handleRun} />}

            {result && (
                <Card
                    title={`${homeTeamName} vs ${awayTeamName}`}
                    subtitle="Simulation results based on historical performance data"
                >
                    <SimulationChart result={result} homeTeam={homeTeamName} awayTeam={awayTeamName} />
                </Card>
            )}
        </div>
    );
}

// ─── ML Prediction Tab ───────────────────────────────────────────────────────

function MLPredictionTab() {
    const [homeTeamId, setHomeTeamId] = useState<number>();
    const [awayTeamId, setAwayTeamId] = useState<number>();
    const [seasonId, setSeasonId] = useState<number>();
    const [prediction, setPrediction] = useState<MLPredictionResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [training, setTraining] = useState(false);

    const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: fetchTeams });
    const { data: seasons } = useQuery({ queryKey: ["seasons"], queryFn: fetchSeasons });

    const { data: modelStatus, refetch: refetchStatus } = useQuery({
        queryKey: ["ml-model-status"],
        queryFn: () => api.get<MLModelStatus>("/predict/ml/status"),
    });

    const handlePredict = async () => {
        if (!homeTeamId || !awayTeamId) return;
        setLoading(true);
        setError(null);
        try {
            const result = await api.post<MLPredictionResult>("/predict/ml", {
                home_team_id: homeTeamId,
                away_team_id: awayTeamId,
                season_id: seasonId,
            });
            setPrediction(result);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Prediction failed");
        } finally {
            setLoading(false);
        }
    };

    const handleTrain = async () => {
        setTraining(true);
        setError(null);
        try {
            await api.post("/predict/ml/train", { season_ids: null });
            refetchStatus();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Training failed");
        } finally {
            setTraining(false);
        }
    };

    return (
        <div className="space-y-6">
            {/* Model Status */}
            <Card padding="md">
                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                            ML Model Status
                        </h3>
                        <p className="text-xs text-[var(--text-muted)]">
                            Gradient-boosted ensemble with calibrated probabilities
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        {modelStatus?.model_available ? (
                            <Badge variant="success">Trained</Badge>
                        ) : (
                            <Badge variant="warning">Not Trained</Badge>
                        )}
                        <Button size="sm" variant="secondary" onClick={handleTrain} loading={training}>
                            {training ? "Training..." : "Train Model"}
                        </Button>
                    </div>
                </div>
                {modelStatus?.metrics && (
                    <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                        <div className="text-center">
                            <p className="text-xs text-[var(--text-muted)]">Accuracy</p>
                            <p className="text-sm font-bold text-[var(--text-primary)]">
                                {(modelStatus.metrics.accuracy * 100).toFixed(1)}%
                            </p>
                        </div>
                        <div className="text-center">
                            <p className="text-xs text-[var(--text-muted)]">Brier Score</p>
                            <p className="text-sm font-bold text-[var(--text-primary)]">
                                {modelStatus.metrics.brier_score.toFixed(4)}
                            </p>
                        </div>
                        <div className="text-center">
                            <p className="text-xs text-[var(--text-muted)]">Log Loss</p>
                            <p className="text-sm font-bold text-[var(--text-primary)]">
                                {modelStatus.metrics.log_loss.toFixed(4)}
                            </p>
                        </div>
                        <div className="text-center">
                            <p className="text-xs text-[var(--text-muted)]">Matches Trained</p>
                            <p className="text-sm font-bold text-[var(--text-primary)]">
                                {modelStatus.metrics.n_matches}
                            </p>
                        </div>
                    </div>
                )}
            </Card>

            {/* Prediction Form */}
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
                    <Select
                        label="Season Context"
                        options={(seasons ?? []).map((s) => ({
                            value: s.id,
                            label: `${s.competition_name} ${s.name}`,
                        }))}
                        value={seasonId}
                        onChange={(v) => setSeasonId(Number(v))}
                        placeholder="(optional)"
                        className="w-full sm:w-56"
                    />
                    <Button
                        onClick={handlePredict}
                        disabled={loading || !homeTeamId || !awayTeamId || homeTeamId === awayTeamId}
                        loading={loading}
                    >
                        Predict
                    </Button>
                </div>
            </Card>

            {error && <ErrorState message={error} />}

            {/* Prediction Results */}
            {prediction && (
                <div className="space-y-4 animate-fade-in">
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
                        <KPICard
                            label={`${prediction.home_team.name} Win`}
                            value={`${(prediction.probabilities.home_win * 100).toFixed(1)}%`}
                        />
                        <KPICard
                            label="Draw"
                            value={`${(prediction.probabilities.draw * 100).toFixed(1)}%`}
                        />
                        <KPICard
                            label={`${prediction.away_team.name} Win`}
                            value={`${(prediction.probabilities.away_win * 100).toFixed(1)}%`}
                        />
                        <KPICard
                            label="Most Likely Score"
                            value={prediction.most_likely_score}
                        />
                        <KPICard
                            label="Over 2.5 Goals"
                            value={`${(prediction.markets.over_2_5 * 100).toFixed(1)}%`}
                        />
                        <KPICard
                            label="BTTS"
                            value={`${(prediction.markets.btts * 100).toFixed(1)}%`}
                        />
                    </div>

                    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                        <Card title="Prediction Summary">
                            <div className="space-y-3">
                                <div className="flex items-center gap-2">
                                    <Badge variant={
                                        prediction.predicted_outcome === "home_win"
                                            ? "success"
                                            : prediction.predicted_outcome === "away_win"
                                                ? "danger"
                                                : "warning"
                                    }>
                                        {prediction.predicted_outcome.replace("_", " ").toUpperCase()}
                                    </Badge>
                                    <span className="text-sm text-[var(--text-muted)]">
                                        Confidence: {(prediction.confidence * 100).toFixed(1)}%
                                    </span>
                                </div>
                                <div className="text-sm text-[var(--text-secondary)]">
                                    <p>
                                        Expected Goals: {prediction.expected_goals.home.toFixed(2)} —{" "}
                                        {prediction.expected_goals.away.toFixed(2)}
                                    </p>
                                    <p className="mt-1 text-xs text-[var(--text-muted)]">
                                        Model: v{prediction.model_version}
                                    </p>
                                </div>
                            </div>
                        </Card>

                        <Card title="Key Features Driving Prediction">
                            <div className="space-y-2 max-h-48 overflow-y-auto">
                                {Object.entries(prediction.feature_contributions)
                                    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
                                    .slice(0, 8)
                                    .map(([feature, value]) => (
                                        <div key={feature} className="flex items-center justify-between text-sm">
                                            <span className="text-[var(--text-secondary)]">
                                                {feature.replace(/_/g, " ")}
                                            </span>
                                            <span
                                                className={`tabular-nums font-medium ${
                                                    value > 0 ? "text-green-500" : "text-red-500"
                                                }`}
                                            >
                                                {value > 0 ? "+" : ""}
                                                {value.toFixed(3)}
                                            </span>
                                        </div>
                                    ))}
                            </div>
                        </Card>
                    </div>
                </div>
            )}
        </div>
    );
}

// ─── Ratings Tab ─────────────────────────────────────────────────────────────

function RatingsTab() {
    const [competitionId, setCompetitionId] = useState<string>("");
    const [ratings, setRatings] = useState<TeamRating[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleFetchRatings = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await api.get<{ ratings: TeamRating[] }>("/predict/ratings", {
                competition_id: competitionId ? Number(competitionId) : undefined,
            });
            setRatings(data.ratings || []);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Failed to load ratings");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-4">
            <Card padding="md">
                <div className="flex items-end gap-4">
                    <div>
                        <label className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
                            Competition ID (optional)
                        </label>
                        <input
                            type="number"
                            value={competitionId}
                            onChange={(e) => setCompetitionId(e.target.value)}
                            className="w-40 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm"
                            placeholder="All"
                        />
                    </div>
                    <Button onClick={handleFetchRatings} disabled={loading}>
                        {loading ? "Loading..." : "Load Ratings"}
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
                                    <tr
                                        key={r.team_id}
                                        className="border-b border-[var(--border-color)]/50"
                                    >
                                        <td className="py-2 pr-4 text-[var(--text-muted)]">{i + 1}</td>
                                        <td className="py-2 pr-4 font-medium text-[var(--text-primary)]">
                                            {r.team_name}
                                        </td>
                                        <td className="py-2 pr-4 tabular-nums">
                                            {r.overall_rating.toFixed(2)}
                                        </td>
                                        <td className="py-2 pr-4 tabular-nums text-green-500">
                                            {r.offensive_strength.toFixed(2)}
                                        </td>
                                        <td className="py-2 pr-4 tabular-nums text-blue-500">
                                            {r.defensive_strength.toFixed(2)}
                                        </td>
                                        <td className="py-2 pr-4">
                                            <span
                                                className={`text-xs ${
                                                    r.form_trend === "improving"
                                                        ? "text-green-500"
                                                        : r.form_trend === "declining"
                                                            ? "text-red-500"
                                                            : "text-[var(--text-muted)]"
                                                }`}
                                            >
                                                {r.form_trend === "improving"
                                                    ? "↑"
                                                    : r.form_trend === "declining"
                                                        ? "↓"
                                                        : "→"}{" "}
                                                {r.form_trend}
                                            </span>
                                        </td>
                                        <td className="py-2">
                                            <span className="rounded-full bg-[var(--bg-secondary)] px-2 py-0.5 text-xs">
                                                {r.confidence}
                                            </span>
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
    return (
        <Card>
            <div className="py-8 text-center text-[var(--text-muted)]">
                <p className="text-lg font-medium">Tournament Simulation</p>
                <p className="mt-2 text-sm">
                    Configure a tournament format (World Cup, Champions League, League) and run Monte
                    Carlo simulations to project team progression probabilities.
                </p>
                <p className="mt-4 text-xs">
                    Use POST /api/v1/predict/tournament with format configuration via the Analysis
                    Workbench or API directly.
                </p>
            </div>
        </Card>
    );
}
