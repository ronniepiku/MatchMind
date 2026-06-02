import { NavLink } from "react-router-dom";
import { clsx } from "clsx";
import {
    LayoutDashboard,
    Users,
    UserCircle,
    Target,
    Activity,
    GitCompare,
    Dice5,
    ChevronLeft,
    ChevronRight,
    Radar,
} from "lucide-react";

interface SidebarProps {
    collapsed: boolean;
    onToggle: () => void;
}

const navigation = [
    { name: "Overview", path: "/", icon: LayoutDashboard },
    { name: "Opponent Profile", path: "/opponent", icon: Target },
    { name: "Player Performance", path: "/player", icon: UserCircle },
    { name: "Team Scorecard", path: "/scorecard", icon: Activity },
    { name: "Match Analysis", path: "/match", icon: Users },
    { name: "Player Comparison", path: "/comparison", icon: GitCompare },
    { name: "Simulation", path: "/simulation", icon: Dice5 },
];

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
    return (
        <aside
            className={clsx(
                "flex h-full flex-col border-r border-[var(--border-color)] bg-[var(--bg-sidebar)] transition-all duration-300",
                collapsed ? "w-16" : "w-60"
            )}
        >
            {/* Logo / Brand */}
            <div className="flex h-14 items-center border-b border-[var(--border-color)] px-4">
                <div className="flex items-center gap-2 overflow-hidden">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-500 text-white">
                        <Radar size={18} strokeWidth={2.5} />
                    </div>
                    {!collapsed && (
                        <span className="whitespace-nowrap text-sm font-semibold text-[var(--text-primary)]">
                            MatchMind
                        </span>
                    )}
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 space-y-1 px-2 py-4">
                {navigation.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        end={item.path === "/"}
                        className={({ isActive }) =>
                            clsx(
                                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                                isActive
                                    ? "bg-accent-500/10 text-accent-500 dark:bg-accent-400/10 dark:text-accent-400"
                                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)] hover:text-[var(--text-primary)]"
                            )
                        }
                    >
                        <item.icon className="h-5 w-5 shrink-0" />
                        {!collapsed && <span className="truncate">{item.name}</span>}
                    </NavLink>
                ))}
            </nav>

            {/* Collapse Toggle */}
            <div className="border-t border-[var(--border-color)] p-2">
                <button
                    onClick={onToggle}
                    className="flex w-full items-center justify-center rounded-lg p-2 text-[var(--text-muted)] hover:bg-[var(--bg-secondary)] hover:text-[var(--text-primary)] transition-colors"
                    aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                >
                    {collapsed ? (
                        <ChevronRight className="h-4 w-4" />
                    ) : (
                        <ChevronLeft className="h-4 w-4" />
                    )}
                </button>
            </div>
        </aside>
    );
}
