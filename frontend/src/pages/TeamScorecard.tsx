import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTeams, fetchSeasons, fetchTeamScorecard } from "@/api/endpoints";
import {
    Card,
    Select,
    Button,
    DataTable,
    Loading,
    ErrorState,
    KPICard,
    Badge,
} from "@/components/shared";
import { PossessionChart } from "@/components/charts";
import type { Column } from "@/components/shared";
import type { SetPieceEfficiency, TransitionMetric } from "@/api/types";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from "recharts";

export default function TeamScorecard() {
    const [teamId, setTeamId] = useState<number>();
    const [seasonId, setSeasonId] = useState<number>();

    const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: fetchTeams });
    const { data: seasons } = useQuery({ queryKey: ["seasons"], queryFn: fetchSeasons });

    const {
        data: scorecard,
        isLoading,
        error,
        refetch,
    } = useQuery({
        queryKey: ["team-scorecard", teamId, seasonId],
        queryFn: () => fetchTeamScorecard(teamId!, seasonId!),
        enabled: !!teamId && !!seasonId,
    });

    const setPieceColumns: Column<SetPieceEfficiency>[] = [
        { key: "type", label: "Type", sortable: true },
        { key: "total", label: "Total", sortable: true, align: "right" },
        { key: "chances_created", label: "Chances", sortable: true, align: "right" },
        { key: "goals", label: "Goals", sortable: true, align: "right" },
        {
            key: "xg",
            label: "xG",
            sortable: true,
            align: "right",
            render: (row) => <span className="tabular-nums">{(row.xg ?? 0).toFixed(2)}</span>,
        },
        {
            key: "conversion_rate",
            label: "Conv. %",
            sortable: true,
            align: "right",
            render: (row) => (
                <span className="tabular-nums">{((row.conversion_rate ?? 0) * 100).toFixed(1)}%</span>
            ),
        },
    ];

    const transitionColumns: Column<TransitionMetric>[] = [
        { key: "metric", label: "Metric", sortable: true },
        {
            key: "value",
            label: "Value",
            sortable: true,
            align: "right",
            render: (row) => (
                <span className="tabular-nums font-medium">{(row.value ?? 0).toFixed(2)}</span>
            ),
        },
        {
            key: "league_avg",
            label: "League Avg",
            sortable: true,
            align: "right",
            render: (row) => (
                <span className="tabular-nums text-[var(--text-muted)]">
                    {(row.league_avg ?? 0).toFixed(2)}
                </span>
            ),
        },
        {
            key: "percentile",
            label: "Percentile",
            sortable: true,
            align: "right",
            render: (row) => {
                const variant =
                    row.percentile >= 75 ? "success" : row.percentile >= 50 ? "info" : row.percentile >= 25 ? "warning" : "danger";
                return <Badge variant={variant}>P{row.percentile}</Badge>;
            },
        },
    ];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">Team Scorecard</h1>
                <p className="mt-1 text-sm text-[var(--text-muted)]">
                    Comprehensive team performance metrics — possession, pressing, transitions, and set-pieces
                </p>
            </div>

            {/* Filters */}
            <Card padding="md">
                <div className="flex flex-wrap items-end gap-4">
                    <Select
                        label="Team"
                        options={(teams ?? []).map((t) => ({ value: t.id, label: t.name }))}
                        value={teamId}
                        onChange={(v) => setTeamId(Number(v))}
                        placeholder="Select team..."
                        className="w-full sm:w-56"
                    />
                    <Select
                        label="Season"
                        options={(seasons ?? []).map((s) => ({
                            value: s.id,
                            label: `${s.competition_name} ${s.name}`,
                        }))}
                        value={seasonId}
                        onChange={(v) => setSeasonId(Number(v))}
                        placeholder="Select season..."
                        className="w-full sm:w-56"
                    />
                    <Button
                        onClick={() => refetch()}
                        disabled={!teamId || !seasonId}
                        loading={isLoading}
                    >
                        Generate Scorecard
                    </Button>
                </div>
            </Card>

            {isLoading && <Loading message="Compiling team scorecard..." />}
            {error && <ErrorState onRetry={() => refetch()} />}

            {scorecard && (
                <div className="space-y-6 animate-fade-in">
                    {/* KPIs */}
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                        {scorecard.kpis.map((kpi) => (
                            <KPICard
                                key={kpi.label}
                                label={kpi.label}
                                value={
                                    kpi.unit === "%"
                                        ? (kpi.value ?? 0).toFixed(1)
                                        : Number.isInteger(kpi.value)
                                            ? String(kpi.value ?? 0)
                                            : (kpi.value ?? 0).toFixed(2)
                                }
                                unit={kpi.unit}
                                change={kpi.change}
                            />
                        ))}
                    </div>

                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                        {/* Possession Style */}
                        <Card title="Possession Profile" subtitle="Breakdown by possession style">
                            <PossessionChart data={scorecard.possession_profile} />
                        </Card>

                        {/* Pressing Intensity */}
                        <Card title="Pressing Intensity" subtitle="Pressures per 90 by pitch zone">
                            <ResponsiveContainer width="100%" height={240}>
                                <BarChart
                                    data={scorecard.pressing_intensity}
                                    margin={{ top: 10, right: 10, left: 10, bottom: 10 }}
                                >
                                    <CartesianGrid
                                        strokeDasharray="3 3"
                                        stroke="var(--border-color)"
                                        strokeOpacity={0.4}
                                    />
                                    <XAxis
                                        dataKey="zone"
                                        tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                                        axisLine={{ stroke: "var(--border-color)" }}
                                        tickLine={false}
                                    />
                                    <YAxis
                                        tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                                        axisLine={{ stroke: "var(--border-color)" }}
                                        tickLine={false}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: "var(--bg-card)",
                                            border: "1px solid var(--border-color)",
                                            borderRadius: "8px",
                                            fontSize: "12px",
                                        }}
                                    />
                                    <Bar
                                        dataKey="pressures_per_90"
                                        fill="var(--color-chart-3)"
                                        radius={[4, 4, 0, 0]}
                                        name="Pressures/90"
                                    />
                                </BarChart>
                            </ResponsiveContainer>
                        </Card>
                    </div>

                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                        {/* Transitions */}
                        <Card title="Transition Metrics" subtitle="Counter-attacks and build-up play vs league">
                            <DataTable columns={transitionColumns} data={scorecard.transitions} compact />
                        </Card>

                        {/* Set Pieces */}
                        <Card title="Set-Piece Efficiency" subtitle="Dead-ball situation outcomes">
                            <DataTable columns={setPieceColumns} data={scorecard.set_pieces} compact />
                        </Card>
                    </div>
                </div>
            )}
        </div>
    );
}
