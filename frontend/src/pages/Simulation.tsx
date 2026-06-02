import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTeams, fetchSeasons, runSimulation } from "@/api/endpoints";
import { Card, Select, Button, Loading, ErrorState } from "@/components/shared";
import { SimulationChart } from "@/components/charts";

export default function Simulation() {
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
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">Match Simulation</h1>
                <p className="mt-1 text-sm text-[var(--text-muted)]">
                    Monte Carlo simulation — 10,000 iterations using Poisson-based match model
                </p>
            </div>

            {/* Configuration */}
            <Card padding="md">
                <div className="flex flex-wrap items-end gap-4">
                    <Select
                        label="Home Team"
                        options={(teams ?? []).filter((t) => t.id !== awayTeamId).map((t) => ({ value: t.id, label: t.name }))}
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
                        options={(teams ?? []).filter((t) => t.id !== homeTeamId).map((t) => ({ value: t.id, label: t.name }))}
                        value={awayTeamId}
                        onChange={(v) => {
                            setAwayTeamId(Number(v));
                            setShouldRun(false);
                        }}
                        placeholder="Select away team..."
                        className="w-full sm:w-52"
                    />
                    <Select
                        label="Based on Season"
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
                <div className="animate-fade-in">
                    <Card
                        title={`${homeTeamName} vs ${awayTeamName}`}
                        subtitle="Simulation results based on historical performance data"
                    >
                        <SimulationChart
                            result={result}
                            homeTeam={homeTeamName}
                            awayTeam={awayTeamName}
                        />
                    </Card>
                </div>
            )}
        </div>
    );
}
