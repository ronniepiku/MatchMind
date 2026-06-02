import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    ReferenceLine,
} from "recharts";
import type { XgTimelineEvent } from "@/api/types";
import { useMemo } from "react";
import { clsx } from "clsx";

interface XgTimelineProps {
    events: XgTimelineEvent[];
    homeTeam: string;
    awayTeam: string;
    className?: string;
    height?: number;
}

export default function XgTimeline({
    events,
    homeTeam,
    awayTeam,
    className,
    height = 300,
}: XgTimelineProps) {
    const chartData = useMemo(() => {
        const minutes = Array.from({ length: 96 }, (_, i) => i);
        let homeCum = 0;
        let awayCum = 0;

        return minutes.map((minute) => {
            const homeEvents = events.filter(
                (e) => e.minute === minute && e.team === homeTeam
            );
            const awayEvents = events.filter(
                (e) => e.minute === minute && e.team === awayTeam
            );

            homeCum += homeEvents.reduce((sum, e) => sum + e.xg, 0);
            awayCum += awayEvents.reduce((sum, e) => sum + e.xg, 0);

            return {
                minute,
                [homeTeam]: parseFloat(homeCum.toFixed(2)),
                [awayTeam]: parseFloat(awayCum.toFixed(2)),
                homeGoal: homeEvents.some((e) => e.outcome === "goal") ? homeCum : null,
                awayGoal: awayEvents.some((e) => e.outcome === "goal") ? awayCum : null,
            };
        });
    }, [events, homeTeam, awayTeam]);

    return (
        <div className={clsx("w-full", className)}>
            <ResponsiveContainer width="100%" height={height}>
                <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                    <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="var(--border-color)"
                        strokeOpacity={0.5}
                    />
                    <XAxis
                        dataKey="minute"
                        tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                        axisLine={{ stroke: "var(--border-color)" }}
                        tickLine={false}
                        label={{ value: "Minute", position: "bottom", fill: "var(--text-muted)", fontSize: 11 }}
                    />
                    <YAxis
                        tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                        axisLine={{ stroke: "var(--border-color)" }}
                        tickLine={false}
                        label={{
                            value: "Cumulative xG",
                            angle: -90,
                            position: "insideLeft",
                            fill: "var(--text-muted)",
                            fontSize: 11,
                        }}
                    />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: "var(--bg-card)",
                            border: "1px solid var(--border-color)",
                            borderRadius: "8px",
                            fontSize: "12px",
                        }}
                        labelStyle={{ color: "var(--text-muted)" }}
                        formatter={(value) => Number(value).toFixed(2)}
                        labelFormatter={(label) => `${label}'`}
                    />
                    <Legend
                        wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }}
                    />
                    <ReferenceLine x={45} stroke="var(--border-color)" strokeDasharray="5 5" label="" />
                    <Line
                        type="stepAfter"
                        dataKey={homeTeam}
                        stroke="var(--color-chart-1)"
                        strokeWidth={2.5}
                        dot={false}
                        activeDot={{ r: 4, strokeWidth: 2 }}
                    />
                    <Line
                        type="stepAfter"
                        dataKey={awayTeam}
                        stroke="var(--color-chart-4)"
                        strokeWidth={2.5}
                        dot={false}
                        activeDot={{ r: 4, strokeWidth: 2 }}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
