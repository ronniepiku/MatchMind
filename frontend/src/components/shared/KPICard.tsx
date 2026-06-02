import { clsx } from "clsx";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface KPICardProps {
    label: string;
    value: string | number;
    change?: number;
    unit?: string;
    trend?: "up" | "down" | "neutral";
    className?: string;
}

export default function KPICard({
    label,
    value,
    change,
    unit,
    trend,
    className,
}: KPICardProps) {
    const computedTrend = trend ?? (change ? (change > 0 ? "up" : change < 0 ? "down" : "neutral") : undefined);

    return (
        <div
            className={clsx(
                "rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-4",
                className
            )}
        >
            <p className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
                {label}
            </p>
            <div className="mt-2 flex items-baseline gap-1">
                <span className="text-2xl font-bold text-[var(--text-primary)] tabular-nums">
                    {value}
                </span>
                {unit && (
                    <span className="text-sm text-[var(--text-muted)]">{unit}</span>
                )}
            </div>
            {change !== undefined && (
                <div className="mt-2 flex items-center gap-1">
                    {computedTrend === "up" && (
                        <TrendingUp className="h-3.5 w-3.5 text-success-500" />
                    )}
                    {computedTrend === "down" && (
                        <TrendingDown className="h-3.5 w-3.5 text-danger-500" />
                    )}
                    {computedTrend === "neutral" && (
                        <Minus className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                    )}
                    <span
                        className={clsx(
                            "text-xs font-medium",
                            computedTrend === "up" && "text-success-500",
                            computedTrend === "down" && "text-danger-500",
                            computedTrend === "neutral" && "text-[var(--text-muted)]"
                        )}
                    >
                        {change > 0 ? "+" : ""}
                        {change.toFixed(1)}%
                    </span>
                    <span className="text-xs text-[var(--text-muted)]">vs prev</span>
                </div>
            )}
        </div>
    );
}
