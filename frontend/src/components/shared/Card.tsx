import { clsx } from "clsx";
import type { ReactNode } from "react";

interface CardProps {
    title?: string;
    subtitle?: string;
    children: ReactNode;
    className?: string;
    padding?: "none" | "sm" | "md" | "lg";
    action?: ReactNode;
}

const paddingMap = {
    none: "",
    sm: "p-3",
    md: "p-4",
    lg: "p-6",
};

export default function Card({
    title,
    subtitle,
    children,
    className,
    padding = "md",
    action,
}: CardProps) {
    return (
        <div
            className={clsx(
                "rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)]",
                paddingMap[padding],
                className
            )}
        >
            {(title || action) && (
                <div
                    className={clsx(
                        "flex items-center justify-between",
                        padding === "none" ? "px-4 pt-4" : "mb-4"
                    )}
                >
                    <div>
                        {title && (
                            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                                {title}
                            </h3>
                        )}
                        {subtitle && (
                            <p className="mt-0.5 text-xs text-[var(--text-muted)]">{subtitle}</p>
                        )}
                    </div>
                    {action && <div>{action}</div>}
                </div>
            )}
            {children}
        </div>
    );
}
