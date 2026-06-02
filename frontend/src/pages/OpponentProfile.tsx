import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTeams, fetchSeasons, fetchOpponentReport } from "@/api/endpoints";
import { Card, Select, Button, DataTable, Loading, ErrorState } from "@/components/shared";
import { DefensiveShapeChart } from "@/components/charts";
import { Badge } from "@/components/shared";
import type { Column } from "@/components/shared";
import type { AttackPattern, KeyPlayer } from "@/api/types";

export default function OpponentProfile() {
    const [teamId, setTeamId] = useState<number>();
    const [seasonId, setSeasonId] = useState<number>();

    const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: fetchTeams });
    const { data: seasons } = useQuery({ queryKey: ["seasons"], queryFn: fetchSeasons });

    const {
        data: report,
        isLoading,
        error,
        refetch,
    } = useQuery({
        queryKey: ["opponent-report", teamId, seasonId],
        queryFn: () => fetchOpponentReport(teamId!, seasonId!),
        enabled: !!teamId && !!seasonId,
    });

    const attackColumns: Column<AttackPattern>[] = [
        { key: "pattern_type", label: "Pattern", sortable: true },
        { key: "frequency", label: "Frequency", sortable: true, align: "right" },
        {
            key: "success_rate",
            label: "Success %",
            sortable: true,
            align: "right",
            render: (row) => (
                <span className="tabular-nums">
                    {(row.success_rate * 100).toFixed(1)}%
                </span>
            ),
        },
        {
            key: "xg_per_attack",
            label: "xG/Attack",
            sortable: true,
            align: "right",
            render: (row) => (
                <span className="tabular-nums font-medium">{row.xg_per_attack.toFixed(3)}</span>
            ),
        },
    ];

    const keyPlayerColumns: Column<KeyPlayer>[] = [
        { key: "player_name", label: "Player", sortable: true },
        { key: "position", label: "Pos", sortable: true, width: "60px" },
        { key: "goals", label: "G", sortable: true, align: "right" },
        { key: "assists", label: "A", sortable: true, align: "right" },
        {
            key: "xg",
            label: "xG",
            sortable: true,
            align: "right",
            render: (row) => <span className="tabular-nums">{row.xg.toFixed(2)}</span>,
        },
        {
            key: "xa",
            label: "xA",
            sortable: true,
            align: "right",
            render: (row) => <span className="tabular-nums">{row.xa.toFixed(2)}</span>,
        },
        { key: "minutes", label: "Mins", sortable: true, align: "right" },
        {
            key: "threat_rating",
            label: "Threat",
            sortable: true,
            align: "right",
            render: (row) => {
                const variant =
                    row.threat_rating >= 8 ? "danger" : row.threat_rating >= 6 ? "warning" : "default";
                return <Badge variant={variant}>{row.threat_rating.toFixed(1)}</Badge>;
            },
        },
    ];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">Opponent Profile</h1>
                <p className="mt-1 text-sm text-[var(--text-muted)]">
                    Pre-match scouting report — attack patterns, defensive structure, and key threats
                </p>
            </div>

            {/* Filters */}
            <Card padding="md">
                <div className="flex flex-wrap items-end gap-4">
                    <Select
                        label="Opponent"
                        options={(teams ?? []).map((t) => ({ value: t.id, label: t.name }))}
                        value={teamId}
                        onChange={(v) => setTeamId(Number(v))}
                        placeholder="Select opponent..."
                        className="w-56"
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
                        className="w-56"
                    />
                    <Button
                        onClick={() => refetch()}
                        disabled={!teamId || !seasonId}
                        loading={isLoading}
                    >
                        Generate Report
                    </Button>
                </div>
            </Card>

            {/* Results */}
            {isLoading && <Loading message="Analysing opponent data..." />}
            {error && <ErrorState onRetry={() => refetch()} />}

            {report && (
                <div className="space-y-6 animate-fade-in">
                    {/* Team name header */}
                    <div className="flex items-center gap-3">
                        <div className="h-1 w-1 rounded-full bg-accent-500" />
                        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                            {report.team_name}
                        </h2>
                    </div>

                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                        {/* Attack Patterns */}
                        <Card title="Attack Patterns" subtitle="How they build and create chances">
                            <DataTable columns={attackColumns} data={report.attack_patterns} compact />
                        </Card>

                        {/* Key Players */}
                        <Card title="Key Threats" subtitle="Highest threat-rated players">
                            <DataTable columns={keyPlayerColumns} data={report.key_players} compact />
                        </Card>
                    </div>

                    {/* Defensive Shape */}
                    <Card title="Defensive Shape" subtitle="Defensive actions by pitch zone">
                        <DefensiveShapeChart data={report.defensive_shape} height={320} />
                    </Card>
                </div>
            )}
        </div>
    );
}
