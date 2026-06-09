import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchTeams, fetchSeasons } from "@/api/endpoints";
import { Card, KPICard } from "@/components/shared";
import {
    Activity,
    Target,
    Users,
    TrendingUp,
    Calendar,
    Database,
    BrainCircuit,
    Search,
    HelpCircle,
} from "lucide-react";

export default function Dashboard() {
    const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: fetchTeams });
    const { data: seasons } = useQuery({ queryKey: ["seasons"], queryFn: fetchSeasons });

    return (
        <div className="space-y-6">
            {/* Page Header */}
            <div>
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                    Performance Overview
                </h1>
                <p className="mt-1 text-sm text-[var(--text-muted)]">
                    Welcome to MatchMind — your football intelligence platform
                </p>
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <KPICard
                    label="Teams Available"
                    value={teams?.length ?? "-"}
                    unit="teams"
                />
                <KPICard
                    label="Seasons Loaded"
                    value={seasons?.length ?? "-"}
                    unit="seasons"
                />
                <KPICard
                    label="Analysis Modules"
                    value={9}
                    unit="active"
                />
                <KPICard
                    label="API Status"
                    value="Online"
                />
            </div>

            {/* Help Tip */}
            <div className="flex items-center gap-2 rounded-lg border border-accent-500/20 bg-accent-500/5 px-4 py-2.5">
                <HelpCircle className="h-4 w-4 shrink-0 text-accent-500" />
                <p className="text-xs text-[var(--text-secondary)]">
                    <span className="font-medium text-[var(--text-primary)]">Tip:</span> Every tool page includes a{" "}
                    <span className="inline-flex items-center gap-0.5 font-medium text-accent-500">
                        <HelpCircle className="inline h-3 w-3" /> Help
                    </span>{" "}
                    button in the top-right corner explaining what it does and how to use it.
                </p>
            </div>

            {/* Navigation Cards */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                <NavigationCard
                    title="Opponent Profile"
                    description="Pre-match scouting reports with attack patterns, defensive shape analysis, and key player identification"
                    icon={Target}
                    href="/opponent"
                    color="var(--color-chart-1)"
                />
                <NavigationCard
                    title="Player Performance"
                    description="Individual player analysis with season summaries, rolling form, radar charts, and squad comparison"
                    icon={Users}
                    href="/player"
                    color="var(--color-chart-2)"
                />
                <NavigationCard
                    title="Team Scorecard"
                    description="Comprehensive team metrics including possession profiles, pressing intensity, and set-piece efficiency"
                    icon={Activity}
                    href="/scorecard"
                    color="var(--color-chart-3)"
                />
                <NavigationCard
                    title="Match Analysis"
                    description="Post-match breakdowns with shot maps, passing networks, xG timelines, and pressure heatmaps"
                    icon={TrendingUp}
                    href="/match"
                    color="var(--color-chart-5)"
                />
                <NavigationCard
                    title="Player Comparison"
                    description="Find similar players using advanced similarity algorithms across normalised per-90 metrics"
                    icon={Database}
                    href="/comparison"
                    color="var(--color-chart-6)"
                />
                <NavigationCard
                    title="Simulations & Predictions"
                    description="Monte Carlo match simulation and ML-powered predictions with scoreline distributions, team ratings, and tournament modelling"
                    icon={BrainCircuit}
                    href="/predictions"
                    color="var(--color-chart-7)"
                />
                <NavigationCard
                    title="Matchday Calendar"
                    description="Fixture schedule with competition sync, pre-match packs, post-match analysis triggers, and status lifecycle tracking"
                    icon={Calendar}
                    href="/matchday"
                    color="var(--color-chart-1)"
                />
                <NavigationCard
                    title="Analysis Workbench"
                    description="Ad-hoc query builder with 21 parameterised queries across 8 categories — run custom analysis on demand"
                    icon={Search}
                    href="/analysis"
                    color="var(--color-chart-2)"
                />
            </div>

            {/* Recent Activity / Data Status */}
            <Card title="Platform Information" subtitle="System status and data availability">
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                    <div className="space-y-3">
                        <h4 className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
                            Data Sources
                        </h4>
                        <ul className="space-y-2">
                            <StatusItem label="StatsBomb Open Data" status="connected" />
                            <StatusItem label="PostgreSQL Database" status="connected" />
                            <StatusItem label="FastAPI Backend" status="connected" />
                        </ul>
                    </div>
                    <div className="space-y-3">
                        <h4 className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
                            Available Analysis
                        </h4>
                        <ul className="space-y-2">
                            <StatusItem label="xG Model (Logistic + Gradient Boosting)" status="ready" />
                            <StatusItem label="Possession Chain Analysis" status="ready" />
                            <StatusItem label="Monte Carlo Simulation" status="ready" />
                            <StatusItem label="ML Match Predictor" status="ready" />
                            <StatusItem label="Player Similarity Engine" status="ready" />
                        </ul>
                    </div>
                </div>
            </Card>
        </div>
    );
}

// ─── Sub-components ───────────────────────────────────────

interface NavigationCardProps {
    title: string;
    description: string;
    icon: React.ComponentType<{ className?: string }>;
    href: string;
    color: string;
}

function NavigationCard({ title, description, icon: Icon, href, color }: NavigationCardProps) {
    return (
        <Link
            to={href}
            className="group block rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-5 transition-all hover:border-accent-500/50 hover:shadow-lg hover:shadow-accent-500/5"
        >
            <div className="flex items-start gap-4">
                <div
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                    style={{ backgroundColor: `color-mix(in srgb, ${color} 15%, transparent)` }}
                >
                    <span style={{ color }}>
                        <Icon className="h-5 w-5" />
                    </span>
                </div>
                <div>
                    <h3 className="text-sm font-semibold text-[var(--text-primary)] group-hover:text-accent-500 transition-colors">
                        {title}
                    </h3>
                    <p className="mt-1 text-xs leading-relaxed text-[var(--text-muted)]">
                        {description}
                    </p>
                </div>
            </div>
        </Link>
    );
}

interface StatusItemProps {
    label: string;
    status: "connected" | "ready" | "offline";
}

function StatusItem({ label, status }: StatusItemProps) {
    const colors = {
        connected: "bg-success-500",
        ready: "bg-accent-500",
        offline: "bg-danger-500",
    };

    return (
        <li className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${colors[status]}`} />
            <span className="text-sm text-[var(--text-secondary)]">{label}</span>
        </li>
    );
}
