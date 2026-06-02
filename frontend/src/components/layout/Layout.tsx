import { useState, useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header from "./Header";

export default function Layout() {
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);
    const location = useLocation();

    // Close mobile sidebar on navigation
    useEffect(() => {
        setMobileOpen(false);
    }, [location.pathname]);

    return (
        <div className="flex h-screen overflow-hidden bg-[var(--bg-primary)]">
            {/* Mobile overlay */}
            {mobileOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/50 lg:hidden"
                    onClick={() => setMobileOpen(false)}
                />
            )}

            {/* Sidebar — hidden on mobile unless toggled */}
            <div
                className={`
                    fixed inset-y-0 left-0 z-50 lg:static lg:z-auto
                    transform transition-transform duration-300 ease-in-out
                    ${mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
                `}
            >
                <Sidebar
                    collapsed={sidebarCollapsed}
                    onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
                    onClose={() => setMobileOpen(false)}
                />
            </div>

            <div className="flex flex-1 flex-col overflow-hidden min-w-0">
                <Header onMenuToggle={() => setMobileOpen(!mobileOpen)} />
                <main className="flex-1 overflow-y-auto p-3 sm:p-4 lg:p-6">
                    <div className="mx-auto max-w-[1800px] animate-fade-in">
                        <Outlet />
                    </div>
                </main>
            </div>
        </div>
    );
}
