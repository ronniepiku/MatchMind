import Pitch from "@/components/pitch/Pitch";
import type { PassingNetwork as PassingNetworkData } from "@/api/types";
import { clsx } from "clsx";

interface PassingNetworkChartProps {
    data: PassingNetworkData;
    className?: string;
    width?: number;
    height?: number;
    teamColor?: string;
}

export default function PassingNetworkChart({
    data,
    className,
    width = 700,
    height = 460,
    teamColor = "#3b82f6",
}: PassingNetworkChartProps) {
    const maxPasses = Math.max(...data.edges.map((e) => e.passes), 1);
    const maxNodePasses = Math.max(...data.nodes.map((n) => n.passes_made), 1);

    return (
        <div className={clsx("space-y-3", className)}>
            <Pitch width={width} height={height}>
                {(xScale, yScale) => (
                    <g>
                        {/* Edges */}
                        {data.edges.map((edge, i) => {
                            const source = data.nodes.find((n) => n.player_name === edge.source);
                            const target = data.nodes.find((n) => n.player_name === edge.target);
                            if (!source || !target) return null;

                            const opacity = 0.2 + (edge.passes / maxPasses) * 0.6;
                            const strokeWidth = 1 + (edge.passes / maxPasses) * 5;

                            return (
                                <line
                                    key={i}
                                    x1={xScale(source.x)}
                                    y1={yScale(source.y)}
                                    x2={xScale(target.x)}
                                    y2={yScale(target.y)}
                                    stroke={teamColor}
                                    strokeWidth={strokeWidth}
                                    strokeOpacity={opacity}
                                    strokeLinecap="round"
                                />
                            );
                        })}

                        {/* Nodes */}
                        {data.nodes.map((node, i) => {
                            const radius = 8 + (node.passes_made / maxNodePasses) * 16;
                            return (
                                <g key={i}>
                                    <circle
                                        cx={xScale(node.x)}
                                        cy={yScale(node.y)}
                                        r={radius}
                                        fill={teamColor}
                                        fillOpacity={0.85}
                                        stroke="white"
                                        strokeWidth={2}
                                    />
                                    <text
                                        x={xScale(node.x)}
                                        y={yScale(node.y) + radius + 14}
                                        textAnchor="middle"
                                        className="text-[10px] fill-white font-medium"
                                        style={{ textShadow: "0 1px 2px rgba(0,0,0,0.8)" }}
                                    >
                                        {node.player_name.split(" ").slice(-1)[0]}
                                    </text>
                                    <title>
                                        {node.player_name} - {node.passes_made} passes ({node.position})
                                    </title>
                                </g>
                            );
                        })}
                    </g>
                )}
            </Pitch>

            <div className="flex items-center gap-6 text-xs text-[var(--text-muted)]">
                <div className="flex items-center gap-1.5">
                    <div className="h-3 w-3 rounded-full" style={{ backgroundColor: teamColor }} />
                    <span>Node size = passes made</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <div className="h-0.5 w-6 rounded" style={{ backgroundColor: teamColor }} />
                    <span>Line weight = pass frequency</span>
                </div>
            </div>
        </div>
    );
}
