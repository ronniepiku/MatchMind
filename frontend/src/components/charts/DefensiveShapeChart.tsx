import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from "recharts";
import type { DefensiveShape } from "@/api/types";
import { clsx } from "clsx";

interface DefensiveShapeChartProps {
    data: DefensiveShape[];
    className?: string;
    height?: number;
}

const metricColors: Record<string, string> = {
    tackles: "var(--color-chart-1)",
    interceptions: "var(--color-chart-2)",
    pressures: "var(--color-chart-3)",
    recoveries: "var(--color-chart-5)",
};

export default function DefensiveShapeChart({
    data,
    className,
    height = 300,
}: DefensiveShapeChartProps) {
    return (
        <div className={clsx("w-full", className)}>
            <ResponsiveContainer width="100%" height={height}>
                <BarChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
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
                        labelStyle={{ color: "var(--text-primary)", fontWeight: 600 }}
                    />
                    <Bar dataKey="tackles" stackId="a" fill={metricColors.tackles} name="Tackles" radius={[0, 0, 0, 0]} />
                    <Bar dataKey="interceptions" stackId="a" fill={metricColors.interceptions} name="Interceptions" />
                    <Bar dataKey="pressures" stackId="a" fill={metricColors.pressures} name="Pressures" />
                    <Bar dataKey="recoveries" stackId="a" fill={metricColors.recoveries} name="Recoveries" radius={[4, 4, 0, 0]} />
                </BarChart>
            </ResponsiveContainer>

            <div className="flex flex-wrap gap-4 mt-2">
                {Object.entries(metricColors).map(([key, color]) => (
                    <div key={key} className="flex items-center gap-1.5">
                        <div className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color }} />
                        <span className="text-xs capitalize text-[var(--text-muted)]">{key}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}
