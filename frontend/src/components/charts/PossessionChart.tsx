import {
    PieChart,
    Pie,
    Cell,
    ResponsiveContainer,
    Tooltip,
} from "recharts";
import type { PossessionProfile } from "@/api/types";
import { clsx } from "clsx";

interface PossessionChartProps {
    data: PossessionProfile[];
    className?: string;
    size?: number;
}

const COLORS = [
    "var(--color-chart-1)",
    "var(--color-chart-2)",
    "var(--color-chart-3)",
    "var(--color-chart-4)",
    "var(--color-chart-5)",
    "var(--color-chart-6)",
];

export default function PossessionChart({
    data,
    className,
    size = 220,
}: PossessionChartProps) {
    if (!data || data.length === 0) {
        return (
            <div className={clsx("flex items-center justify-center", className)} style={{ height: size }}>
                <p className="text-sm text-[var(--text-muted)]">No possession data available</p>
            </div>
        );
    }

    return (
        <div className={clsx("flex items-center gap-6", className)}>
            <div style={{ width: size, height: size }}>
                <ResponsiveContainer width={size} height={size}>
                    <PieChart>
                        <Pie
                            data={data}
                            cx="50%"
                            cy="50%"
                            innerRadius={size * 0.28}
                            outerRadius={size * 0.42}
                            dataKey="percentage"
                            nameKey="style"
                            paddingAngle={2}
                            strokeWidth={0}
                            isAnimationActive={false}
                        >
                            {data.map((_, idx) => (
                                <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                            ))}
                        </Pie>
                        <Tooltip
                            contentStyle={{
                                backgroundColor: "var(--bg-card)",
                                border: "1px solid var(--border-color)",
                                borderRadius: "8px",
                                fontSize: "12px",
                            }}
                            formatter={(value) => `${Number(value).toFixed(1)}%`}
                        />
                    </PieChart>
                </ResponsiveContainer>
            </div>

            <div className="space-y-2">
                {data.map((item, idx) => (
                    <div key={item.style} className="flex items-center gap-2">
                        <div
                            className="h-3 w-3 rounded-sm shrink-0"
                            style={{ backgroundColor: COLORS[idx % COLORS.length] }}
                        />
                        <div className="flex items-baseline gap-2">
                            <span className="text-sm font-medium text-[var(--text-primary)] tabular-nums">
                                {(item.percentage ?? 0).toFixed(1)}%
                            </span>
                            <span className="text-xs text-[var(--text-muted)]">{item.style}</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
