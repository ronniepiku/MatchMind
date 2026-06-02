import { useMemo } from "react";
import Pitch from "@/components/pitch/Pitch";
import type { ShotEvent } from "@/api/types";
import { clsx } from "clsx";

interface ShotMapProps {
    shots: ShotEvent[];
    className?: string;
    width?: number;
    height?: number;
    half?: "full" | "attacking";
    title?: string;
}

const outcomeColors: Record<string, string> = {
    goal: "#22c55e",
    saved: "#f59e0b",
    blocked: "#64748b",
    off_target: "#ef4444",
    post: "#8b5cf6",
};

const outcomeLabels: Record<string, string> = {
    goal: "Goal",
    saved: "Saved",
    blocked: "Blocked",
    off_target: "Off Target",
    post: "Post",
};

export default function ShotMap({
    shots,
    className,
    width = 700,
    height = 460,
    half = "attacking",
    title,
}: ShotMapProps) {
    const stats = useMemo(() => {
        const goals = shots.filter((s) => s.outcome === "goal").length;
        const totalXg = shots.reduce((sum, s) => sum + s.xg, 0);
        return { goals, totalXg, totalShots: shots.length };
    }, [shots]);

    return (
        <div className={clsx("space-y-3", className)}>
            {title && (
                <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h4>
                    <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
                        <span>
                            <strong className="text-[var(--text-primary)]">{stats.totalShots}</strong> shots
                        </span>
                        <span>
                            <strong className="text-[var(--text-primary)]">{stats.goals}</strong> goals
                        </span>
                        <span>
                            <strong className="text-[var(--text-primary)]">{stats.totalXg.toFixed(2)}</strong> xG
                        </span>
                    </div>
                </div>
            )}

            <Pitch width={width} height={height} half={half}>
                {(xScale, yScale) => (
                    <g>
                        {shots.map((shot, i) => (
                            <g key={i}>
                                <circle
                                    cx={xScale(shot.x)}
                                    cy={yScale(shot.y)}
                                    r={Math.max(4, Math.sqrt(shot.xg) * 20)}
                                    fill={outcomeColors[shot.outcome] ?? "#64748b"}
                                    fillOpacity={0.75}
                                    stroke={outcomeColors[shot.outcome] ?? "#64748b"}
                                    strokeWidth={1.5}
                                    strokeOpacity={1}
                                />
                                <title>
                                    {shot.player_name} ({shot.minute}') - xG: {shot.xg.toFixed(2)} - {shot.outcome}
                                </title>
                            </g>
                        ))}
                    </g>
                )}
            </Pitch>

            {/* Legend */}
            <div className="flex flex-wrap gap-4">
                {Object.entries(outcomeLabels).map(([key, label]) => (
                    <div key={key} className="flex items-center gap-1.5">
                        <div
                            className="h-3 w-3 rounded-full"
                            style={{ backgroundColor: outcomeColors[key] }}
                        />
                        <span className="text-xs text-[var(--text-muted)]">{label}</span>
                    </div>
                ))}
                <div className="flex items-center gap-1.5 ml-4">
                    <div className="flex items-center gap-1">
                        <div className="h-2 w-2 rounded-full bg-surface-400" />
                        <div className="h-3.5 w-3.5 rounded-full bg-surface-400/30" />
                        <div className="h-5 w-5 rounded-full bg-surface-400/20" />
                    </div>
                    <span className="text-xs text-[var(--text-muted)]">xG value (size)</span>
                </div>
            </div>
        </div>
    );
}
