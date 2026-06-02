import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
    fetchTeams,
    fetchSeasons,
    fetchPlayers,
    fetchSimilarPlayers,
    fetchPlayerRadar,
} from "@/api/endpoints";
import { Card, Select, DataTable, Loading, Badge } from "@/components/shared";
import { PlayerRadar } from "@/components/charts";
import type { Column } from "@/components/shared";
import type { SimilarPlayer } from "@/api/types";

export default function PlayerComparison() {
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

    const { data: similarPlayers, isLoading } = useQuery({
        queryKey: ["similar-players", playerId, seasonId],
        queryFn: () => fetchSimilarPlayers(playerId!, 15, seasonId),
        enabled: !!playerId,
    });

    const { data: playerRadar } = useQuery({
        queryKey: ["player-radar-comparison", playerId, seasonId],
        queryFn: () => fetchPlayerRadar(playerId!, seasonId!),
        enabled: !!playerId && !!seasonId,
    });

    const columns: Column<SimilarPlayer>[] = [
        {
            key: "similarity_score",
            label: "Match",
            sortable: true,
            align: "center",
            width: "80px",
            render: (row) => {
                const pct = (row.similarity_score * 100).toFixed(0);
                const variant =
                    row.similarity_score >= 0.9
                        ? "success"
                        : row.similarity_score >= 0.8
                            ? "info"
                            : "default";
                return <Badge variant={variant}>{pct}%</Badge>;
            },
        },
        { key: "player_name", label: "Player", sortable: true },
        { key: "team", label: "Team", sortable: true },
        { key: "position", label: "Pos", sortable: true, width: "60px" },
        { key: "age", label: "Age", sortable: true, align: "right" },
        { key: "minutes", label: "Mins", sortable: true, align: "right" },
    ];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">Player Comparison</h1>
                <p className="mt-1 text-sm text-[var(--text-muted)]">
                    Find similar players using cosine similarity across normalised per-90 performance vectors
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
                            setPlayerId(undefined);
                        }}
                        placeholder="Select season..."
                        className="w-full sm:w-52"
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
                        className="w-full sm:w-64"
                    />
                </div>
            </Card>

            {isLoading && <Loading message="Computing player similarity..." />}

            {similarPlayers && (
                <div className="space-y-6 animate-fade-in">
                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
                        {/* Radar */}
                        {playerRadar && playerRadar.length > 0 && (
                            <Card
                                title="Player Profile"
                                subtitle="Percentile radar vs. positional peers"
                                className="xl:col-span-1"
                            >
                                <PlayerRadar metrics={playerRadar} size={300} />
                            </Card>
                        )}

                        {/* Similar Players Table */}
                        <Card
                            title="Most Similar Players"
                            subtitle={`Top ${similarPlayers.length} matches by statistical profile`}
                            className="xl:col-span-2"
                        >
                            <DataTable columns={columns} data={similarPlayers} />
                        </Card>
                    </div>
                </div>
            )}
        </div>
    );
}
