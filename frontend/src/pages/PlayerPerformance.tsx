import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
    fetchTeams,
    fetchSeasons,
    fetchPlayers,
    fetchPlayerSummary,
    fetchPlayerRollingForm,
    fetchPlayerRadar,
    fetchSquadComparison,
} from "@/api/endpoints";
import {
    Card,
    Select,
    DataTable,
    Loading,
    KPICard,
} from "@/components/shared";
import { PlayerRadar, RollingFormChart } from "@/components/charts";
import type { Column } from "@/components/shared";
import type { SquadComparisonPlayer } from "@/api/types";

export default function PlayerPerformance() {
    const [teamId, setTeamId] = useState<number>();
    const [seasonId, setSeasonId] = useState<number>();
    const [playerId, setPlayerId] = useState<number>();

    const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: fetchTeams });
    const { data: seasons } = useQuery({ queryKey: ["seasons"], queryFn: fetchSeasons });
    const { data: players } = useQuery({
        queryKey: ["players", teamId, seasonId],
        queryFn: () => fetchPlayers(teamId!, seasonId!),
        enabled: !!teamId && !!seasonId,
    });

    const { data: summary, isLoading: loadingSummary } = useQuery({
        queryKey: ["player-summary", playerId, seasonId],
        queryFn: () => fetchPlayerSummary(playerId!, seasonId!),
        enabled: !!playerId && !!seasonId,
    });

    const { data: rollingForm } = useQuery({
        queryKey: ["player-rolling", playerId, seasonId],
        queryFn: () => fetchPlayerRollingForm(playerId!, seasonId!),
        enabled: !!playerId && !!seasonId,
    });

    const { data: radarMetrics } = useQuery({
        queryKey: ["player-radar", playerId, seasonId],
        queryFn: () => fetchPlayerRadar(playerId!, seasonId!),
        enabled: !!playerId && !!seasonId,
    });

    const { data: squadComparison } = useQuery({
        queryKey: ["squad-comparison", teamId, seasonId],
        queryFn: () => fetchSquadComparison(teamId!, seasonId!),
        enabled: !!teamId && !!seasonId,
    });

    const squadColumns: Column<SquadComparisonPlayer>[] = [
        { key: "player_name", label: "Player", sortable: true },
        { key: "position", label: "Pos", sortable: true, width: "60px" },
        { key: "minutes", label: "Mins", sortable: true, align: "right" },
        { key: "goals", label: "G", sortable: true, align: "right" },
        { key: "assists", label: "A", sortable: true, align: "right" },
        {
            key: "xg_per_90",
            label: "xG/90",
            sortable: true,
            align: "right",
            render: (row) => <span className="tabular-nums">{row.xg_per_90.toFixed(2)}</span>,
        },
        {
            key: "xa_per_90",
            label: "xA/90",
            sortable: true,
            align: "right",
            render: (row) => <span className="tabular-nums">{row.xa_per_90.toFixed(2)}</span>,
        },
        {
            key: "rating",
            label: "Rating",
            sortable: true,
            align: "right",
            render: (row) => (
                <span className="tabular-nums font-semibold">{row.rating.toFixed(1)}</span>
            ),
        },
    ];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">Player Performance</h1>
                <p className="mt-1 text-sm text-[var(--text-muted)]">
                    Individual analysis — season summary, rolling form, and percentile rankings
                </p>
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
                            setPlayerId(undefined);
                        }}
                        placeholder="Select team..."
                        className="w-52"
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
                            setPlayerId(undefined);
                        }}
                        placeholder="Select season..."
                        className="w-52"
                    />
                    <Select
                        label="Player"
                        options={(players ?? []).map((p) => ({
                            value: p.id,
                            label: `${p.name} (${p.position})`,
                        }))}
                        value={playerId}
                        onChange={(v) => setPlayerId(Number(v))}
                        placeholder="Select player..."
                        disabled={!players?.length}
                        className="w-64"
                    />
                </div>
            </Card>

            {loadingSummary && <Loading message="Loading player data..." />}

            {/* Player Summary */}
            {summary && (
                <div className="space-y-6 animate-fade-in">
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                        <KPICard label="Matches" value={summary.matches_played} />
                        <KPICard label="Minutes" value={summary.minutes.toLocaleString()} />
                        <KPICard label="Goals" value={summary.goals} />
                        <KPICard label="Assists" value={summary.assists} />
                        <KPICard label="xG/90" value={summary.xg_per_90.toFixed(2)} />
                        <KPICard label="xA/90" value={summary.xa_per_90.toFixed(2)} />
                    </div>

                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                        {/* Radar Chart */}
                        {radarMetrics && radarMetrics.length > 0 && (
                            <Card title="Percentile Radar" subtitle="Performance vs. positional peers">
                                <PlayerRadar metrics={radarMetrics} size={340} />
                            </Card>
                        )}

                        {/* Rolling Form */}
                        {rollingForm && rollingForm.length > 0 && (
                            <Card title="Rolling Form" subtitle="5-match rolling average xG and xA">
                                <RollingFormChart data={rollingForm} />
                            </Card>
                        )}
                    </div>

                    {/* Additional stats */}
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
                        <KPICard label="Pass Accuracy" value={`${summary.pass_accuracy.toFixed(1)}%`} />
                        <KPICard label="Passes Completed" value={summary.passes_completed} />
                        <KPICard label="Tackles Won" value={summary.tackles_won} />
                        <KPICard label="Interceptions" value={summary.interceptions} />
                        <KPICard label="Pressures" value={summary.pressures} />
                        <KPICard label="Total xG" value={summary.xg.toFixed(2)} />
                    </div>
                </div>
            )}

            {/* Squad Comparison */}
            {squadComparison && squadComparison.length > 0 && (
                <Card title="Squad Comparison" subtitle="All players ranked by performance rating">
                    <DataTable
                        columns={squadColumns}
                        data={squadComparison}
                        highlightRow={(row) => row.player_name === players?.find((p) => p.id === playerId)?.name}
                    />
                </Card>
            )}
        </div>
    );
}
