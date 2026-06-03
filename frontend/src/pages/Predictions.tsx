import { useState } from "react";
import { Card, KPICard, Button, ErrorState } from "@/components/shared";
import { api } from "@/api";
import type { MatchPrediction, TeamRating } from "@/api/types";

export default function Predictions() {
    const [homeTeamId, setHomeTeamId] = useState("");
    const [awayTeamId, setAwayTeamId] = useState("");
    const [competitionId, setCompetitionId] = useState("");
    const [venue, setVenue] = useState<"home" | "away" | "neutral">("home");
    const [prediction, setPrediction] = useState<MatchPrediction | null>(null);
    const [ratings, setRatings] = useState<TeamRating[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<"predict" | "ratings" | "simulate">("predict");

    const handlePredict = async () => {
        if (!homeTeamId || !awayTeamId) return;
        setLoading(true);
        setError(null);
        try {
            const result = await api.post<MatchPrediction>("/predict/match", {
                team_a_id: Number(homeTeamId),
                team_b_id: Number(awayTeamId),
                competition_id: competitionId ? Number(competitionId) : undefined,
                venue_type: venue,
            });
            setPrediction(result);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Prediction failed");
        } finally {
            setLoading(false);
        }
    };

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
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                    Prediction Engine
                </h1>
                <p className="text-sm text-[var(--text-muted)]">
                    Match outcome forecasting, team ratings, and tournament simulation
                </p>
            </div>

            {/* Tabs */}
            <div className="flex gap-2 border-b border-[var(--border-color)] pb-2">
                {(["predict", "ratings", "simulate"] as const).map((tab) => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${activeTab === tab
                            ? "bg-accent-500/10 text-accent-500"
                            : "text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]"
                            }`}
                    >
                        {tab === "predict" ? "Match Predictor" : tab === "ratings" ? "Team Ratings" : "Tournament Sim"}
                    </button>
                ))}
            </div>

            {error && <ErrorState message={error} />}

            {/* Match Predictor */}
            {activeTab === "predict" && (
                <div className="space-y-4">
                    <Card>
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
                            <div>
                                <label className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
                                    Home Team ID
                                </label>
                                <input
                                    type="number"
                                    value={homeTeamId}
                                    onChange={(e) => setHomeTeamId(e.target.value)}
                                    className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm"
                                    placeholder="e.g. 1"
                                />
                            </div>
                            <div>
                                <label className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
                                    Away Team ID
                                </label>
                                <input
                                    type="number"
                                    value={awayTeamId}
                                    onChange={(e) => setAwayTeamId(e.target.value)}
                                    className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm"
                                    placeholder="e.g. 2"
                                />
                            </div>
                            <div>
                                <label className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
                                    Venue
                                </label>
                                <select
                                    value={venue}
                                    onChange={(e) => setVenue(e.target.value as any)}
                                    className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm"
                                >
                                    <option value="home">Home</option>
                                    <option value="away">Away</option>
                                    <option value="neutral">Neutral</option>
                                </select>
                            </div>
                            <div className="flex items-end">
                                <Button onClick={handlePredict} disabled={loading || !homeTeamId || !awayTeamId}>
                                    {loading ? "Predicting..." : "Predict"}
                                </Button>
                            </div>
                        </div>
                    </Card>

                    {prediction && (
                        <div className="space-y-4">
                            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
                                <KPICard
                                    label="Home Win"
                                    value={`${(prediction.team_a_win_prob * 100).toFixed(1)}%`}
                                />
                                <KPICard
                                    label="Draw"
                                    value={`${(prediction.draw_prob * 100).toFixed(1)}%`}
                                />
                                <KPICard
                                    label="Away Win"
                                    value={`${(prediction.team_b_win_prob * 100).toFixed(1)}%`}
                                />
                                <KPICard
                                    label="Most Likely Score"
                                    value={`${prediction.most_likely_score[0]}-${prediction.most_likely_score[1]}`}
                                />
                            </div>

                            <Card>
                                <h3 className="mb-2 font-semibold text-[var(--text-primary)]">
                                    Key Factors
                                </h3>
                                <div className="flex items-center gap-2 mb-2">
                                    <span className="rounded-full bg-accent-500/10 px-2 py-0.5 text-xs font-medium text-accent-500">
                                        Confidence: {prediction.confidence}
                                    </span>
                                    <span className="text-xs text-[var(--text-muted)]">
                                        xG: {prediction.team_a_expected_xg.toFixed(2)} vs {prediction.team_b_expected_xg.toFixed(2)}
                                    </span>
                                </div>
                                <ul className="space-y-1">
                                    {prediction.key_factors?.map((factor, i) => (
                                        <li key={i} className="text-sm text-[var(--text-secondary)]">
                                            • {factor}
                                        </li>
                                    ))}
                                </ul>
                            </Card>
                        </div>
                    )}
                </div>
            )}

            {/* Team Ratings */}
            {activeTab === "ratings" && (
                <div className="space-y-4">
                    <Card>
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
                                                <td className="py-2 pr-4">{r.overall_rating.toFixed(2)}</td>
                                                <td className="py-2 pr-4 text-green-500">{r.offensive_strength.toFixed(2)}</td>
                                                <td className="py-2 pr-4 text-blue-500">{r.defensive_strength.toFixed(2)}</td>
                                                <td className="py-2 pr-4">
                                                    <span className={`text-xs ${r.form_trend === "improving" ? "text-green-500" : r.form_trend === "declining" ? "text-red-500" : "text-[var(--text-muted)]"}`}>
                                                        {r.form_trend === "improving" ? "↑" : r.form_trend === "declining" ? "↓" : "→"} {r.form_trend}
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
            )}

            {/* Tournament Simulation */}
            {activeTab === "simulate" && (
                <Card>
                    <div className="py-8 text-center text-[var(--text-muted)]">
                        <p className="text-lg font-medium">Tournament Simulation</p>
                        <p className="mt-2 text-sm">
                            Configure a tournament format (World Cup, Champions League, League) and run
                            Monte Carlo simulations to project team progression probabilities.
                        </p>
                        <p className="mt-4 text-xs">
                            Use POST /api/v1/predict/tournament with format configuration.
                        </p>
                    </div>
                </Card>
            )}
        </div>
    );
}
