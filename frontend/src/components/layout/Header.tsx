import { useTheme } from "@/hooks/useTheme";
import { Sun, Moon, Bell } from "lucide-react";

export default function Header() {
    const { theme, toggleTheme } = useTheme();

    return (
        <header className="flex h-14 items-center justify-between border-b border-[var(--border-color)] bg-[var(--bg-sidebar)] px-6">
            <div className="flex items-center gap-4">
                <h2 className="text-sm font-medium text-[var(--text-secondary)]">
                    Performance Analytics Platform
                </h2>
            </div>

            <div className="flex items-center gap-2">
                {/* Connection status indicator */}
                <div className="flex items-center gap-2 rounded-full bg-[var(--bg-secondary)] px-3 py-1.5">
                    <div className="h-2 w-2 rounded-full bg-success-500 animate-pulse-subtle" />
                    <span className="text-xs font-medium text-[var(--text-secondary)]">
                        API Connected
                    </span>
                </div>

                {/* Notifications */}
                <button
                    className="relative rounded-lg p-2 text-[var(--text-muted)] hover:bg-[var(--bg-secondary)] hover:text-[var(--text-primary)] transition-colors"
                    aria-label="Notifications"
                >
                    <Bell className="h-4 w-4" />
                </button>

                {/* Theme Toggle */}
                <button
                    onClick={toggleTheme}
                    className="rounded-lg p-2 text-[var(--text-muted)] hover:bg-[var(--bg-secondary)] hover:text-[var(--text-primary)] transition-colors"
                    aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
                >
                    {theme === "dark" ? (
                        <Sun className="h-4 w-4" />
                    ) : (
                        <Moon className="h-4 w-4" />
                    )}
                </button>
            </div>
        </header>
    );
}
