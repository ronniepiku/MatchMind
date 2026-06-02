import { useMemo } from "react";
import { clsx } from "clsx";
import type { RadarMetric } from "@/api/types";

interface PlayerRadarProps {
    metrics: RadarMetric[];
    className?: string;
    size?: number;
    color?: string;
    comparisonMetrics?: RadarMetric[];
    comparisonColor?: string;
}

export default function PlayerRadar({
    metrics,
    className,
    size = 320,
    color = "#3b82f6",
    comparisonMetrics,
    comparisonColor = "#ef4444",
}: PlayerRadarProps) {
    const center = size / 2;
    const radius = (size / 2) * 0.75;
    const levels = 5;

    const points = useMemo(() => {
        const angleStep = (2 * Math.PI) / metrics.length;
        return metrics.map((m, i) => {
            const angle = angleStep * i - Math.PI / 2;
            const r = (m.percentile / 100) * radius;
            return {
                x: center + r * Math.cos(angle),
                y: center + r * Math.sin(angle),
                labelX: center + (radius + 20) * Math.cos(angle),
                labelY: center + (radius + 20) * Math.sin(angle),
                metric: m,
                angle,
            };
        });
    }, [metrics, center, radius]);

    const comparisonPoints = useMemo(() => {
        if (!comparisonMetrics) return null;
        const angleStep = (2 * Math.PI) / comparisonMetrics.length;
        return comparisonMetrics.map((m, i) => {
            const angle = angleStep * i - Math.PI / 2;
            const r = (m.percentile / 100) * radius;
            return {
                x: center + r * Math.cos(angle),
                y: center + r * Math.sin(angle),
            };
        });
    }, [comparisonMetrics, center, radius]);

    const pathData = points.map((p) => `${p.x},${p.y}`).join(" ");
    const compPathData = comparisonPoints
        ? comparisonPoints.map((p) => `${p.x},${p.y}`).join(" ")
        : null;

    return (
        <div className={clsx("flex items-center justify-center", className)}>
            <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
                {/* Background levels */}
                {Array.from({ length: levels }, (_, i) => {
                    const levelRadius = (radius / levels) * (i + 1);
                    const levelPoints = metrics
                        .map((_, mi) => {
                            const angle = ((2 * Math.PI) / metrics.length) * mi - Math.PI / 2;
                            return `${center + levelRadius * Math.cos(angle)},${center + levelRadius * Math.sin(angle)}`;
                        })
                        .join(" ");

                    return (
                        <polygon
                            key={i}
                            points={levelPoints}
                            fill="none"
                            stroke="var(--border-color)"
                            strokeWidth={i === levels - 1 ? 1.5 : 0.5}
                            strokeOpacity={0.5}
                        />
                    );
                })}

                {/* Axis lines */}
                {points.map((p, i) => (
                    <line
                        key={i}
                        x1={center}
                        y1={center}
                        x2={center + radius * Math.cos(p.angle)}
                        y2={center + radius * Math.sin(p.angle)}
                        stroke="var(--border-color)"
                        strokeWidth={0.5}
                        strokeOpacity={0.3}
                    />
                ))}

                {/* Comparison data polygon */}
                {compPathData && (
                    <polygon
                        points={compPathData}
                        fill={comparisonColor}
                        fillOpacity={0.1}
                        stroke={comparisonColor}
                        strokeWidth={1.5}
                        strokeOpacity={0.6}
                    />
                )}

                {/* Main data polygon */}
                <polygon
                    points={pathData}
                    fill={color}
                    fillOpacity={0.15}
                    stroke={color}
                    strokeWidth={2}
                />

                {/* Data points */}
                {points.map((p, i) => (
                    <g key={i}>
                        <circle cx={p.x} cy={p.y} r={4} fill={color} stroke="white" strokeWidth={1.5} />
                        <title>
                            {p.metric.metric}: {p.metric.value.toFixed(2)} (P{p.metric.percentile})
                        </title>
                    </g>
                ))}

                {/* Labels */}
                {points.map((p, i) => (
                    <text
                        key={`label-${i}`}
                        x={p.labelX}
                        y={p.labelY}
                        textAnchor="middle"
                        dominantBaseline="middle"
                        className="text-[10px] fill-[var(--text-muted)]"
                    >
                        {p.metric.metric}
                    </text>
                ))}
            </svg>
        </div>
    );
}
