import { useRef, useEffect } from "react";
import * as d3 from "d3";
import { clsx } from "clsx";

// Standard pitch dimensions (StatsBomb: 120x80)
const PITCH_LENGTH = 120;
const PITCH_WIDTH = 80;
const PADDING = 4;

interface PitchProps {
    width?: number;
    height?: number;
    className?: string;
    children?: (
        xScale: d3.ScaleLinear<number, number>,
        yScale: d3.ScaleLinear<number, number>
    ) => React.ReactNode;
    orientation?: "horizontal" | "vertical";
    half?: "full" | "attacking" | "defensive";
}

export default function Pitch({
    width = 700,
    height = 460,
    className,
    children,
    orientation = "horizontal",
    half = "full",
}: PitchProps) {
    const svgRef = useRef<SVGSVGElement>(null);

    const effectiveLength = half === "full" ? PITCH_LENGTH : PITCH_LENGTH / 2;
    const xDomain = half === "defensive" ? [0, 60] : half === "attacking" ? [60, 120] : [0, 120];

    const xScale = d3
        .scaleLinear()
        .domain(orientation === "horizontal" ? xDomain : [0, PITCH_WIDTH])
        .range([PADDING, width - PADDING]);

    const yScale = d3
        .scaleLinear()
        .domain(orientation === "horizontal" ? [0, PITCH_WIDTH] : xDomain)
        .range([PADDING, height - PADDING]);

    useEffect(() => {
        if (!svgRef.current) return;
        const svg = d3.select(svgRef.current);
        svg.selectAll(".pitch-markings").remove();

        const g = svg.append("g").attr("class", "pitch-markings");
        const lineColor = "rgba(255, 255, 255, 0.6)";
        const lineWidth = 1.5;

        const x = (v: number) => xScale(orientation === "horizontal" ? v : v);
        const y = (v: number) => yScale(orientation === "horizontal" ? v : v);

        // Pitch outline
        g.append("rect")
            .attr("x", x(xDomain[0]))
            .attr("y", y(0))
            .attr("width", x(xDomain[1]) - x(xDomain[0]))
            .attr("height", y(PITCH_WIDTH) - y(0))
            .attr("fill", "none")
            .attr("stroke", lineColor)
            .attr("stroke-width", lineWidth);

        // Centre line
        if (half === "full") {
            g.append("line")
                .attr("x1", x(60))
                .attr("y1", y(0))
                .attr("x2", x(60))
                .attr("y2", y(80))
                .attr("stroke", lineColor)
                .attr("stroke-width", lineWidth);

            // Centre circle
            g.append("circle")
                .attr("cx", x(60))
                .attr("cy", y(40))
                .attr("r", xScale(10) - xScale(0))
                .attr("fill", "none")
                .attr("stroke", lineColor)
                .attr("stroke-width", lineWidth);

            // Centre spot
            g.append("circle")
                .attr("cx", x(60))
                .attr("cy", y(40))
                .attr("r", 2)
                .attr("fill", lineColor);
        }

        // Left penalty area (if visible)
        if (xDomain[0] <= 18) {
            g.append("rect")
                .attr("x", x(0))
                .attr("y", y(18))
                .attr("width", x(18) - x(0))
                .attr("height", y(62) - y(18))
                .attr("fill", "none")
                .attr("stroke", lineColor)
                .attr("stroke-width", lineWidth);

            // Left 6-yard box
            g.append("rect")
                .attr("x", x(0))
                .attr("y", y(30))
                .attr("width", x(6) - x(0))
                .attr("height", y(50) - y(30))
                .attr("fill", "none")
                .attr("stroke", lineColor)
                .attr("stroke-width", lineWidth);

            // Left penalty spot
            g.append("circle")
                .attr("cx", x(12))
                .attr("cy", y(40))
                .attr("r", 2)
                .attr("fill", lineColor);
        }

        // Right penalty area (if visible)
        if (xDomain[1] >= 102) {
            g.append("rect")
                .attr("x", x(102))
                .attr("y", y(18))
                .attr("width", x(120) - x(102))
                .attr("height", y(62) - y(18))
                .attr("fill", "none")
                .attr("stroke", lineColor)
                .attr("stroke-width", lineWidth);

            // Right 6-yard box
            g.append("rect")
                .attr("x", x(114))
                .attr("y", y(30))
                .attr("width", x(120) - x(114))
                .attr("height", y(50) - y(30))
                .attr("fill", "none")
                .attr("stroke", lineColor)
                .attr("stroke-width", lineWidth);

            // Right penalty spot
            g.append("circle")
                .attr("cx", x(108))
                .attr("cy", y(40))
                .attr("r", 2)
                .attr("fill", lineColor);
        }

        // Goal lines (goal posts)
        if (xDomain[0] <= 0) {
            g.append("rect")
                .attr("x", x(0) - 3)
                .attr("y", y(36))
                .attr("width", 3)
                .attr("height", y(44) - y(36))
                .attr("fill", lineColor)
                .attr("rx", 1);
        }
        if (xDomain[1] >= 120) {
            g.append("rect")
                .attr("x", x(120))
                .attr("y", y(36))
                .attr("width", 3)
                .attr("height", y(44) - y(36))
                .attr("fill", lineColor)
                .attr("rx", 1);
        }
    }, [width, height, orientation, half, xScale, yScale, xDomain, effectiveLength]);

    return (
        <div className={clsx("pitch-container relative w-full overflow-hidden", className)}>
            <svg
                ref={svgRef}
                width="100%"
                height="auto"
                viewBox={`0 0 ${width} ${height}`}
                preserveAspectRatio="xMidYMid meet"
                className="rounded-lg w-full h-auto"
                style={{ background: "var(--color-pitch-green)", maxWidth: width }}
            >
                {/* Pitch markings rendered by D3 */}
                {/* Data overlay rendered by React */}
                {children?.(xScale, yScale)}
            </svg>
        </div>
    );
}

export { PITCH_LENGTH, PITCH_WIDTH };
