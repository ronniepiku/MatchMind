import { clsx } from "clsx";
import type { SimulationResult } from "@/api/types";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell,
} from "recharts";

interface SimulationChartProps {
    result: SimulationResult;
    homeTeam: string;
    awayTeam: string;
    className?: string;
}

export default function SimulationChart({
    result,
    homeTeam,
    awayTeam,
    className,
}: SimulationChartProps) {
    const outcomeData = [
        { name: homeTeam, probability: result.home_win_prob * 100, color: "var(--color-chart-1)" },
        { name: "Draw", probability: result.draw_prob * 100, color: "var(--color-chart-3)" },
        { name: awayTeam, probability: result.away_win_prob * 100, color: "var(--color-chart-4)" },
    ];

    const topScorelines = result.scoreline_distribution
        .sort((a, b) => b.probability - a.probability)
        .slice(0, 10);

    return (
        <div className={clsx("space-y-6", className)}>
            {/* Win probability bars */}
            <div className="space-y-3">
                <h4 className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
                    Match Outcome Probability
                </h4>
                <div className="flex h-8 w-full overflow-hidden rounded-lg">
                    {outcomeData.map((item) => (
                        <div
                            key={item.name}
                            className="flex items-center justify-center text-xs font-bold text-white transition-all"
                            style={{
                                width: `${item.probability}%`,
                                backgroundColor: item.color,
                                minWidth: item.probability > 5 ? undefined : "24px",
                            }}
                        >
                            {item.probability > 8 && `${item.probability.toFixed(0)}%`}
                        </div>
                    ))}
                </div>
                <div className="flex justify-between text-xs text-[var(--text-muted)]">
                    <span>{homeTeam} Win</span>
                    <span>Draw</span>
                    <span>{awayTeam} Win</span>
                </div>
            </div>

            {/* Scoreline distribution */}
            <div className="space-y-3">
                <h4 className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
                    Most Likely Scorelines
                </h4>
                <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={topScorelines} margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" strokeOpacity={0.4} />
                        <XAxis
                            dataKey="score"
                            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                            axisLine={{ stroke: "var(--border-color)" }}
                            tickLine={false}
                        />
                        <YAxis
                            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                            axisLine={{ stroke: "var(--border-color)" }}
                            tickLine={false}
                            tickFormatter={(val) => `${(val * 100).toFixed(0)}%`}
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: "var(--bg-card)",
                                border: "1px solid var(--border-color)",
                                borderRadius: "8px",
                                fontSize: "12px",
                            }}
                            formatter={(value) => `${(Number(value) * 100).toFixed(1)}%`}
                        />
                        <Bar dataKey="probability" radius={[4, 4, 0, 0]}>
                            {topScorelines.map((entry, idx) => (
                                <Cell
                                    key={idx}
                                    fill={
                                        entry.score === result.most_likely_score
                                            ? "var(--color-accent-500)"
                                            : "var(--color-surface-500)"
                                    }
                                    fillOpacity={entry.score === result.most_likely_score ? 1 : 0.6}
                                />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>

            {/* Key stats */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3 text-center">
                    <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                        Expected Score
                    </p>
                    <p className="mt-1 text-lg font-bold text-[var(--text-primary)] tabular-nums">
                        {result.expected_home_goals.toFixed(1)} - {result.expected_away_goals.toFixed(1)}
                    </p>
                </div>
                <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3 text-center">
                    <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                        Most Likely
                    </p>
                    <p className="mt-1 text-lg font-bold text-[var(--text-primary)] tabular-nums">
                        {result.most_likely_score}
                    </p>
                </div>
                <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3 text-center">
                    <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                        Over 2.5 Goals
                    </p>
                    <p className="mt-1 text-lg font-bold text-[var(--text-primary)] tabular-nums">
                        {(result.over_2_5_prob * 100).toFixed(0)}%
                    </p>
                </div>
                <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3 text-center">
                    <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                        BTTS
                    </p>
                    <p className="mt-1 text-lg font-bold text-[var(--text-primary)] tabular-nums">
                        {(result.btts_prob * 100).toFixed(0)}%
                    </p>
                </div>
            </div>
        </div>
    );
}
