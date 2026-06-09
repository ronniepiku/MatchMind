import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
    fetchTeams,
    fetchSeasons,
    fetchMatches,
    fetchShotMap,
    fetchPassingNetwork,
    fetchXgTimeline,
    fetchPressureMap,
} from "@/api/endpoints";
import { Card, Select, Loading, HelpPanel } from "@/components/shared";
import {
    ShotMap,
    PassingNetworkChart,
    XgTimeline,
    PressureHeatmap,
} from "@/components/charts";

export default function MatchAnalysis() {
    const [teamId, setTeamId] = useState<number>();
    const [seasonId, setSeasonId] = useState<number>();
    const [matchId, setMatchId] = useState<number>();

    const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: fetchTeams });
    const { data: seasons } = useQuery({ queryKey: ["seasons"], queryFn: fetchSeasons });
    const { data: matches } = useQuery({
        queryKey: ["matches", teamId, seasonId],
        queryFn: () => fetchMatches(teamId!, seasonId!),
        enabled: !!teamId && !!seasonId,
    });

    const { data: shots, isLoading: loadingShots } = useQuery({
        queryKey: ["shots", matchId],
        queryFn: () => fetchShotMap(matchId!),
        enabled: !!matchId,
    });

    const { data: passingNetwork } = useQuery({
        queryKey: ["passing-network", matchId, teamId],
        queryFn: () => fetchPassingNetwork(matchId!, teamId!),
        enabled: !!matchId && !!teamId,
    });

    const { data: xgEvents } = useQuery({
        queryKey: ["xg-timeline", matchId],
        queryFn: () => fetchXgTimeline(matchId!),
        enabled: !!matchId,
    });

    const { data: pressureEvents } = useQuery({
        queryKey: ["pressure-map", matchId, teamId],
        queryFn: () => fetchPressureMap(matchId!, teamId!),
        enabled: !!matchId && !!teamId,
    });

    const selectedMatch = matches?.find((m) => m.id === matchId);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-[var(--text-primary)]">Match Analysis</h1>
                    <p className="mt-1 text-sm text-[var(--text-muted)]">
                        Post-match breakdown — shot maps, passing networks, xG timelines, and pressure zones
                    </p>
                </div>
                <HelpPanel
                    title="Match Analysis"
                    sections={[
                        { heading: "What it does", content: "Provides a detailed post-match breakdown with interactive visualisations including shot maps, passing networks, expected goals timelines, and pressure heatmaps." },
                        { heading: "How it works", content: "Processes individual match event data to generate spatial visualisations — plotting shots by location and xG, mapping pass combinations between players, and showing press intensity zones." },
                        { heading: "How to use", content: "Select a team, season, and specific match. The page loads four visualisations: a pitch shot map, the passing network for your team, a cumulative xG timeline, and a pressure heatmap." },
                    ]}
                />
            </div>

            {/* Filters */}
            <Card padding="md">
                <div className="flex flex-wrap items-end gap-4">
                    <Select
                        label="Team"
                        options={(teams ?? []).map((t) => ({ value: t.id, label: t.name }))}
                        value={teamId}
                        onChange={(v) => {
                            setTeamId(Number(v));
                            setMatchId(undefined);
                        }}
                        placeholder="Select team..."
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
                            setMatchId(undefined);
                        }}
                        placeholder="Select season..."
                        className="w-full sm:w-52"
                    />
                    <Select
                        label="Match"
                        options={(matches ?? []).map((m) => ({
                            value: m.id,
                            label: `${m.home_team} ${m.home_score}-${m.away_score} ${m.away_team}`,
                        }))}
                        value={matchId}
                        onChange={(v) => setMatchId(Number(v))}
                        placeholder="Select match..."
                        disabled={!matches?.length}
                        className="w-full sm:w-80"
                    />
                </div>
            </Card>

            {loadingShots && <Loading message="Loading match data..." />}

            {matchId && selectedMatch && (
                <div className="space-y-6 animate-fade-in">
                    {/* Match header */}
                    <div className="flex items-center justify-center gap-6 rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-6">
                        <div className="text-right">
                            <p className="text-lg font-bold text-[var(--text-primary)]">
                                {selectedMatch.home_team}
                            </p>
                        </div>
                        <div className="text-center">
                            <p className="text-3xl font-bold text-[var(--text-primary)] tabular-nums">
                                {selectedMatch.home_score} — {selectedMatch.away_score}
                            </p>
                            <p className="mt-1 text-xs text-[var(--text-muted)]">
                                {selectedMatch.date} · {selectedMatch.competition}
                            </p>
                        </div>
                        <div className="text-left">
                            <p className="text-lg font-bold text-[var(--text-primary)]">
                                {selectedMatch.away_team}
                            </p>
                        </div>
                    </div>

                    {/* xG Timeline */}
                    {xgEvents && xgEvents.length > 0 && (
                        <Card title="xG Timeline" subtitle="Cumulative expected goals over match time">
                            <XgTimeline
                                events={xgEvents}
                                homeTeam={selectedMatch.home_team}
                                awayTeam={selectedMatch.away_team}
                                height={280}
                            />
                        </Card>
                    )}

                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                        {/* Shot Map */}
                        {shots && shots.length > 0 && (
                            <Card title="Shot Map" padding="sm">
                                <ShotMap shots={shots} title="" half="attacking" width={580} height={380} />
                            </Card>
                        )}

                        {/* Passing Network */}
                        {passingNetwork && (
                            <Card title="Passing Network" padding="sm">
                                <PassingNetworkChart data={passingNetwork} width={580} height={380} />
                            </Card>
                        )}
                    </div>

                    {/* Pressure Heatmap */}
                    {pressureEvents && pressureEvents.length > 0 && (
                        <Card title="Pressure Heatmap" subtitle="Defensive pressing zones and intensity">
                            <PressureHeatmap events={pressureEvents} width={700} height={460} />
                        </Card>
                    )}
                </div>
            )}
        </div>
    );
}
