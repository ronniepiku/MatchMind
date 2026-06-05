import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, KPICard, Button, ErrorState, Badge } from "@/components/shared";
import {
    fetchCalendar,
    fetchExternalFixtures,
    syncCompetitionFixtures,
} from "@/api/endpoints";
import type { ExternalFixture } from "@/api/types";

const COMPETITIONS = [
    { code: "PL", name: "Premier League", icon: "🏴󠁧󠁢󠁥󠁮󠁧󠁿" },
    { code: "CL", name: "Champions League", icon: "🇪🇺" },
    { code: "WC", name: "World Cup", icon: "🌍" },
] as const;

type CompetitionCode = (typeof COMPETITIONS)[number]["code"];

const STATUS_COLORS: Record<string, string> = {
    scheduled: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    SCHEDULED: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    TIMED: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    preview_generated: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    in_progress: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
    IN_PLAY: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
    completed: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    FINISHED: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    reviewed: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
};

export default function MatchdayCalendar() {
    const [selectedCompetition, setSelectedCompetition] = useState<CompetitionCode>("PL");
    const queryClient = useQueryClient();

    // Fetch external fixtures from football-data.org
    const {
        data: externalData,
        isLoading: loadingExternal,
        error: externalError,
        refetch: refetchExternal,
    } = useQuery({
        queryKey: ["external-fixtures", selectedCompetition],
        queryFn: () => fetchExternalFixtures(selectedCompetition),
    });

    // Also fetch local calendar for synced fixtures
    const { data: calendar } = useQuery({
        queryKey: ["matchday-calendar"],
        queryFn: () => fetchCalendar(30, 7),
    });

    // Sync mutation
    const syncMutation = useMutation({
        mutationFn: (code: string) => syncCompetitionFixtures(code),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["matchday-calendar"] });
        },
    });

    const competitionInfo = COMPETITIONS.find((c) => c.code === selectedCompetition)!;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                        Matchday Calendar
                    </h1>
                    <p className="mt-1 text-sm text-[var(--text-muted)]">
                        Upcoming fixtures from live data — select a competition to view schedule
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => syncMutation.mutate(selectedCompetition)}
                        loading={syncMutation.isPending}
                    >
                        Sync to DB
                    </Button>
                    <Button size="sm" onClick={() => refetchExternal()} disabled={loadingExternal}>
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Competition Selector */}
            <div className="flex gap-3">
                {COMPETITIONS.map((comp) => (
                    <button
                        key={comp.code}
                        onClick={() => setSelectedCompetition(comp.code)}
                        className={`flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-medium transition-all ${
                            selectedCompetition === comp.code
                                ? "bg-accent-500/10 text-accent-500 ring-2 ring-accent-500/30"
                                : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                        }`}
                    >
                        <span className="text-lg">{comp.icon}</span>
                        <span>{comp.name}</span>
                    </button>
                ))}
            </div>

            {/* Sync Status */}
            {syncMutation.isSuccess && (
                <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700 dark:border-green-800 dark:bg-green-900/20 dark:text-green-400">
                    Synced {syncMutation.data.total} fixtures — {syncMutation.data.created} new,{" "}
                    {syncMutation.data.skipped} already existed
                </div>
            )}
            {syncMutation.isError && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
                    {syncMutation.error instanceof Error
                        ? syncMutation.error.message
                        : "Sync failed — check API key configuration"}
                </div>
            )}

            {/* KPI Summary */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <KPICard
                    label="Total Upcoming"
                    value={externalData?.count ?? 0}
                />
                <KPICard
                    label="This Week"
                    value={
                        externalData?.fixtures.filter((f) => {
                            if (!f.match_date) return false;
                            const d = new Date(f.match_date);
                            const now = new Date();
                            const diff = (d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
                            return diff >= 0 && diff <= 7;
                        }).length ?? 0
                    }
                />
                <KPICard
                    label="Competition"
                    value={competitionInfo.name}
                />
                <KPICard
                    label="Synced Locally"
                    value={calendar?.upcoming_count ?? 0}
                />
            </div>

            {/* Error State */}
            {externalError && (
                <ErrorState
                    message={
                        externalError instanceof Error
                            ? externalError.message.includes("503")
                                ? "API key not configured. Set FOOTBALL_DATA_API_KEY in your .env file (free at football-data.org)"
                                : externalError.message
                            : "Failed to load fixtures"
                    }
                    onRetry={() => refetchExternal()}
                />
            )}

            {/* Loading */}
            {loadingExternal && (
                <Card>
                    <div className="flex items-center justify-center py-8">
                        <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent-500 border-t-transparent" />
                        <span className="ml-3 text-sm text-[var(--text-muted)]">
                            Loading {competitionInfo.name} fixtures...
                        </span>
                    </div>
                </Card>
            )}

            {/* Fixtures List */}
            {externalData && externalData.fixtures.length > 0 && (
                <Card>
                    <h2 className="mb-4 text-lg font-semibold text-[var(--text-primary)]">
                        {competitionInfo.icon} {competitionInfo.name} — Upcoming Fixtures
                    </h2>
                    <div className="space-y-2">
                        {groupByMatchday(externalData.fixtures).map(([matchday, fixtures]) => (
                            <div key={matchday} className="mb-4">
                                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                                    {matchday}
                                </h3>
                                <div className="space-y-2">
                                    {fixtures.map((fixture) => (
                                        <FixtureRow key={fixture.external_id} fixture={fixture} />
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </Card>
            )}

            {externalData && externalData.fixtures.length === 0 && !loadingExternal && (
                <Card>
                    <div className="py-8 text-center text-[var(--text-muted)]">
                        <p className="text-lg font-medium">No upcoming fixtures</p>
                        <p className="mt-1 text-sm">
                            The {competitionInfo.name} has no scheduled matches at this time.
                        </p>
                    </div>
                </Card>
            )}
        </div>
    );
}

// ─── Fixture Row Component ───────────────────────────────────────────────────

function FixtureRow({ fixture }: { fixture: ExternalFixture }) {
    const matchDate = fixture.match_date ? new Date(fixture.match_date) : null;
    const now = new Date();
    const daysUntil = matchDate
        ? Math.ceil((matchDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
        : null;

    return (
        <div className="flex items-center justify-between rounded-lg border border-[var(--border-color)] p-3 transition-colors hover:bg-[var(--bg-secondary)]">
            <div className="flex items-center gap-4">
                {/* Date */}
                <div className="w-16 text-center">
                    <div className="text-xs text-[var(--text-muted)]">
                        {matchDate
                            ? matchDate.toLocaleDateString("en-GB", {
                                  day: "numeric",
                                  month: "short",
                              })
                            : "TBD"}
                    </div>
                    {fixture.kick_off && (
                        <div className="text-xs font-medium text-[var(--text-secondary)]">
                            {fixture.kick_off}
                        </div>
                    )}
                    {daysUntil !== null && daysUntil >= 0 && (
                        <div className="mt-0.5 text-[10px] font-semibold text-accent-500">
                            {daysUntil === 0
                                ? "TODAY"
                                : daysUntil === 1
                                  ? "TOMORROW"
                                  : `${daysUntil} days`}
                        </div>
                    )}
                </div>

                {/* Teams */}
                <div>
                    <div className="font-medium text-[var(--text-primary)]">
                        {fixture.home_team.name}{" "}
                        <span className="text-[var(--text-muted)]">vs</span>{" "}
                        {fixture.away_team.name}
                    </div>
                    <div className="text-xs text-[var(--text-muted)]">
                        {fixture.stage || `Matchday ${fixture.matchday}`}
                    </div>
                </div>
            </div>

            {/* Status badge */}
            <Badge
                variant={
                    fixture.status === "TIMED" || fixture.status === "SCHEDULED"
                        ? "info"
                        : fixture.status === "IN_PLAY"
                          ? "warning"
                          : fixture.status === "FINISHED"
                            ? "success"
                            : "default"
                }
            >
                {fixture.status.replace("_", " ")}
            </Badge>
        </div>
    );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function groupByMatchday(fixtures: ExternalFixture[]): [string, ExternalFixture[]][] {
    const groups = new Map<string, ExternalFixture[]>();

    for (const fixture of fixtures) {
        const key = fixture.stage
            ? fixture.stage
            : fixture.matchday
              ? `Matchday ${fixture.matchday}`
              : "Scheduled";

        const existing = groups.get(key) || [];
        existing.push(fixture);
        groups.set(key, existing);
    }

    return Array.from(groups.entries());
}
