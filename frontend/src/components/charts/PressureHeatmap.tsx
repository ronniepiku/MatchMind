import { useMemo, useRef, useEffect } from "react";
import * as d3 from "d3";
import Pitch from "@/components/pitch/Pitch";
import type { PressureEvent } from "@/api/types";
import { clsx } from "clsx";

interface PressureHeatmapProps {
    events: PressureEvent[];
    className?: string;
    width?: number;
    height?: number;
}

export default function PressureHeatmap({
    events,
    className,
    width = 700,
    height = 460,
}: PressureHeatmapProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    const stats = useMemo(() => {
        const successful = events.filter((e) => e.success).length;
        return {
            total: events.length,
            successful,
            successRate: events.length > 0 ? (successful / events.length) * 100 : 0,
        };
    }, [events]);

    useEffect(() => {
        if (!canvasRef.current || events.length === 0) return;

        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        canvas.width = width;
        canvas.height = height;
        ctx.clearRect(0, 0, width, height);

        // Create density data using kernel density estimation
        const xScale = d3.scaleLinear().domain([0, 120]).range([4, width - 4]);
        const yScale = d3.scaleLinear().domain([0, 80]).range([4, height - 4]);

        // Simple 2D kernel density
        const gridSize = 4;
        const cols = Math.ceil(width / gridSize);
        const rows = Math.ceil(height / gridSize);
        const density = new Float32Array(cols * rows);

        const bandwidth = 18;
        let maxDensity = 0;

        events.forEach((event) => {
            const ex = xScale(event.x);
            const ey = yScale(event.y);

            const startCol = Math.max(0, Math.floor((ex - bandwidth * 2) / gridSize));
            const endCol = Math.min(cols - 1, Math.ceil((ex + bandwidth * 2) / gridSize));
            const startRow = Math.max(0, Math.floor((ey - bandwidth * 2) / gridSize));
            const endRow = Math.min(rows - 1, Math.ceil((ey + bandwidth * 2) / gridSize));

            for (let row = startRow; row <= endRow; row++) {
                for (let col = startCol; col <= endCol; col++) {
                    const px = col * gridSize + gridSize / 2;
                    const py = row * gridSize + gridSize / 2;
                    const dist = Math.sqrt((px - ex) ** 2 + (py - ey) ** 2);
                    const weight = Math.exp(-(dist * dist) / (2 * bandwidth * bandwidth));
                    const idx = row * cols + col;
                    density[idx] += weight;
                    maxDensity = Math.max(maxDensity, density[idx]);
                }
            }
        });

        // Render heatmap
        const colorScale = d3
            .scaleSequential(d3.interpolateInferno)
            .domain([0, maxDensity]);

        for (let row = 0; row < rows; row++) {
            for (let col = 0; col < cols; col++) {
                const val = density[row * cols + col];
                if (val > maxDensity * 0.05) {
                    const color = d3.color(colorScale(val));
                    if (color) {
                        color.opacity = Math.min(0.75, val / maxDensity);
                        ctx.fillStyle = color.formatRgb();
                        ctx.fillRect(col * gridSize, row * gridSize, gridSize, gridSize);
                    }
                }
            }
        }
    }, [events, width, height]);

    return (
        <div className={clsx("space-y-3", className)}>
            <div className="relative w-full overflow-hidden">
                <Pitch width={width} height={height} />
                <canvas
                    ref={canvasRef}
                    className="absolute inset-0 rounded-lg pointer-events-none w-full h-full"
                    style={{ mixBlendMode: "screen" }}
                />
            </div>

            <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
                <div className="flex items-center gap-4">
                    <span>
                        <strong className="text-[var(--text-primary)]">{stats.total}</strong> pressures
                    </span>
                    <span>
                        <strong className="text-[var(--text-primary)]">{stats.successRate.toFixed(1)}%</strong>{" "}
                        success rate
                    </span>
                </div>
                <div className="flex items-center gap-1">
                    <span>Low</span>
                    <div className="h-2 w-24 rounded bg-gradient-to-r from-[#000004] via-[#b73779] to-[#fcffa4]" />
                    <span>High</span>
                </div>
            </div>
        </div>
    );
}
