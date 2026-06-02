import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
} from "recharts";
import type { RollingFormDataPoint } from "@/api/types";
import { clsx } from "clsx";

interface RollingFormChartProps {
    data: RollingFormDataPoint[];
    className?: string;
    height?: number;
}

export default function RollingFormChart({
    data,
    className,
    height = 280,
}: RollingFormChartProps) {
    return (
        <div className={clsx("w-full", className)}>
            <ResponsiveContainer width="100%" height={height}>
                <LineChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                    <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="var(--border-color)"
                        strokeOpacity={0.4}
                    />
                    <XAxis
                        dataKey="match_label"
                        tick={{ fill: "var(--text-muted)", fontSize: 10 }}
                        axisLine={{ stroke: "var(--border-color)" }}
                        tickLine={false}
                        angle={-45}
                        textAnchor="end"
                        height={60}
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
                        formatter={(value, name) => [
                            Number(value).toFixed(2),
                            name === "xg_rolling" ? "xG (5-match avg)" : name === "xa_rolling" ? "xA (5-match avg)" : String(name),
                        ]}
                    />
                    <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }} />
                    <Line
                        type="monotone"
                        dataKey="xg"
                        stroke="var(--color-chart-1)"
                        strokeWidth={1}
                        strokeOpacity={0.3}
                        dot={{ r: 2, fill: "var(--color-chart-1)" }}
                        name="xG (match)"
                    />
                    <Line
                        type="monotone"
                        dataKey="xg_rolling"
                        stroke="var(--color-chart-1)"
                        strokeWidth={2.5}
                        dot={false}
                        name="xG (5-match avg)"
                    />
                    <Line
                        type="monotone"
                        dataKey="xa"
                        stroke="var(--color-chart-2)"
                        strokeWidth={1}
                        strokeOpacity={0.3}
                        dot={{ r: 2, fill: "var(--color-chart-2)" }}
                        name="xA (match)"
                    />
                    <Line
                        type="monotone"
                        dataKey="xa_rolling"
                        stroke="var(--color-chart-2)"
                        strokeWidth={2.5}
                        dot={false}
                        name="xA (5-match avg)"
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
