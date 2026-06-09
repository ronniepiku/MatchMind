import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, KPICard, Button, ErrorState, Badge, HelpPanel } from "@/components/shared";
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

export default function MatchdayCalendar() {
    const [selectedCompetition, setSelectedCompetition] = useState<CompetitionCode>("PL");
    const [teamFilter, setTeamFilter] = useState("");
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

    // Derive unique team names from fixtures for the filter
    const teamNames = useMemo(() => {
        if (!externalData?.fixtures) return [];
        const names = new Set<string>();
        for (const f of externalData.fixtures) {
            names.add(f.home_team.name);
            names.add(f.away_team.name);
        }
        return Array.from(names).sort();
    }, [externalData]);

    // Filter fixtures by selected team
    const filteredFixtures = useMemo(() => {
        if (!externalData?.fixtures) return [];
        if (!teamFilter) return externalData.fixtures;
        return externalData.fixtures.filter(
            (f) => f.home_team.name === teamFilter || f.away_team.name === teamFilter
        );
    }, [externalData, teamFilter]);

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
                    <HelpPanel
                        title="Matchday Calendar"
                        sections={[
                            { heading: "What it does", content: "Displays upcoming and recent fixtures across competitions, with live sync from football-data.org and the ability to store fixtures locally for matchday workflows." },
                            { heading: "How it works", content: "Fetches fixture data from external APIs (Premier League, Champions League, World Cup) and merges it with locally stored match records. Supports status tracking through the matchday lifecycle." },
                            { heading: "How to use", content: "Select a competition tab to view fixtures. Use Sync to DB to store fixtures locally for pre-match and post-match workflows. Filter by team to focus on specific opponents." },
                        ]}
                    />
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
            <div className="flex flex-wrap items-center gap-3">
                {COMPETITIONS.map((comp) => (
                    <button
                        key={comp.code}
                        onClick={() => { setSelectedCompetition(comp.code); setTeamFilter(""); }}
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

                {/* Team Filter */}
                {teamNames.length > 0 && (
                    <select
                        value={teamFilter}
                        onChange={(e) => setTeamFilter(e.target.value)}
                        className="ml-auto rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2.5 text-sm text-[var(--text-primary)] focus:border-accent-500 focus:outline-none focus:ring-1 focus:ring-accent-500"
                    >
                        <option value="">All teams</option>
                        {teamNames.map((name) => (
                            <option key={name} value={name}>{name}</option>
                        ))}
                    </select>
                )}
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
                    value={filteredFixtures.length}
                />
                <KPICard
                    label="This Week"
                    value={
                        filteredFixtures.filter((f) => {
                            if (!f.match_date) return false;
                            const d = new Date(f.match_date);
                            const now = new Date();
                            const diff = (d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
                            return diff >= 0 && diff <= 7;
                        }).length
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
            {externalData && filteredFixtures.length > 0 && (
                <Card>
                    <h2 className="mb-4 text-lg font-semibold text-[var(--text-primary)]">
                        {competitionInfo.icon} {competitionInfo.name} — Upcoming Fixtures
                        {teamFilter && <span className="ml-2 text-sm font-normal text-[var(--text-muted)]">({teamFilter})</span>}
                    </h2>
                    <div className="space-y-2">
                        {groupByMatchday(filteredFixtures).map(([matchday, fixtures]) => (
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

            {externalData && filteredFixtures.length === 0 && !loadingExternal && (
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
