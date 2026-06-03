import { useState, useEffect, useCallback } from "react";
import { Card, KPICard, Button, ErrorState } from "@/components/shared";
import { api } from "@/api";
import type { CalendarResponse } from "@/api/types";

const STATUS_COLORS: Record<string, string> = {
    scheduled: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    preview_generated: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    in_progress: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
    completed: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    reviewed: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
};

export default function MatchdayCalendar() {
    const [calendar, setCalendar] = useState<CalendarResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchCalendar = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await api.get<CalendarResponse>("/matchday/calendar", {
                days_ahead: 14,
                days_behind: 7,
            });
            setCalendar(data);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Failed to load calendar");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchCalendar();
    }, [fetchCalendar]);

    const generatePreMatchPack = async (fixtureId: number) => {
        try {
            await api.get<unknown>(`/matchday/fixtures/${fixtureId}/pre-match`);
            fetchCalendar();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Failed to generate pack");
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                        Matchday Calendar
                    </h1>
                    <p className="text-sm text-[var(--text-muted)]">
                        Fixture management and operational workflow
                    </p>
                </div>
                <Button onClick={fetchCalendar} disabled={loading}>
                    {loading ? "Refreshing..." : "Refresh"}
                </Button>
            </div>

            {error && <ErrorState message={error} />}

            {/* KPI Summary */}
            {calendar && (
                <>
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
                        <KPICard label="Upcoming (14 days)" value={calendar.upcoming_count} />
                        <KPICard
                            label="Need Preview"
                            value={calendar.needing_preview}
                        />
                        <KPICard
                            label="Need Review"
                            value={calendar.needing_review}
                        />
                        <KPICard
                            label="Reviewed"
                            value={calendar.status_counts.reviewed}
                        />
                    </div>

                    {/* Upcoming Fixtures */}
                    <Card>
                        <h2 className="mb-4 text-lg font-semibold text-[var(--text-primary)]">
                            Upcoming Fixtures
                        </h2>
                        {calendar.upcoming_fixtures.length === 0 ? (
                            <p className="text-sm text-[var(--text-muted)]">No upcoming fixtures.</p>
                        ) : (
                            <div className="space-y-3">
                                {calendar.upcoming_fixtures.map((fixture) => (
                                    <div
                                        key={fixture.fixture_id}
                                        className="flex items-center justify-between rounded-lg border border-[var(--border-color)] p-3"
                                    >
                                        <div className="flex items-center gap-4">
                                            <div className="text-center">
                                                <div className="text-xs text-[var(--text-muted)]">
                                                    {fixture.match_date
                                                        ? new Date(fixture.match_date).toLocaleDateString("en-GB", {
                                                            day: "numeric",
                                                            month: "short",
                                                        })
                                                        : "TBD"}
                                                </div>
                                                {fixture.days_until !== null && (
                                                    <div className="text-xs font-medium text-accent-500">
                                                        {fixture.days_until === 0
                                                            ? "Today"
                                                            : fixture.days_until === 1
                                                                ? "Tomorrow"
                                                                : `${fixture.days_until}d`}
                                                    </div>
                                                )}
                                            </div>
                                            <div>
                                                <div className="font-medium text-[var(--text-primary)]">
                                                    {fixture.home_team.name} vs {fixture.away_team.name}
                                                </div>
                                                <div className="text-xs text-[var(--text-muted)]">
                                                    {fixture.competition_name} • {fixture.stage}
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span
                                                className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[fixture.status] || STATUS_COLORS.scheduled}`}
                                            >
                                                {fixture.status.replace("_", " ")}
                                            </span>
                                            {fixture.status === "scheduled" && fixture.days_until !== null && fixture.days_until <= 3 && (
                                                <button
                                                    onClick={() => generatePreMatchPack(fixture.fixture_id)}
                                                    className="rounded-lg bg-accent-500 px-2 py-1 text-xs font-medium text-white hover:bg-accent-600"
                                                >
                                                    Generate Pack
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </Card>

                    {/* Recent Results */}
                    <Card>
                        <h2 className="mb-4 text-lg font-semibold text-[var(--text-primary)]">
                            Recent Results
                        </h2>
                        {calendar.recent_results.length === 0 ? (
                            <p className="text-sm text-[var(--text-muted)]">No recent results.</p>
                        ) : (
                            <div className="space-y-3">
                                {calendar.recent_results.map((fixture) => (
                                    <div
                                        key={fixture.fixture_id}
                                        className="flex items-center justify-between rounded-lg border border-[var(--border-color)] p-3"
                                    >
                                        <div className="flex items-center gap-4">
                                            <div className="text-xs text-[var(--text-muted)]">
                                                {fixture.match_date
                                                    ? new Date(fixture.match_date).toLocaleDateString("en-GB", {
                                                        day: "numeric",
                                                        month: "short",
                                                    })
                                                    : ""}
                                            </div>
                                            <div>
                                                <div className="font-medium text-[var(--text-primary)]">
                                                    {fixture.home_team.name} vs {fixture.away_team.name}
                                                </div>
                                                <div className="text-xs text-[var(--text-muted)]">
                                                    {fixture.competition_name}
                                                </div>
                                            </div>
                                        </div>
                                        <span
                                            className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[fixture.status] || ""}`}
                                        >
                                            {fixture.status.replace("_", " ")}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </Card>
                </>
            )}
        </div>
    );
}
