import { clsx } from "clsx";
import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";

interface ButtonProps {
    children: ReactNode;
    onClick?: () => void;
    variant?: "primary" | "secondary" | "ghost";
    size?: "sm" | "md" | "lg";
    disabled?: boolean;
    loading?: boolean;
    className?: string;
    type?: "button" | "submit";
}

const variantStyles = {
    primary:
        "bg-accent-500 text-white hover:bg-accent-600 focus:ring-accent-500/50",
    secondary:
        "border border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-primary)] hover:bg-[var(--bg-card)]",
    ghost:
        "text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)] hover:text-[var(--text-primary)]",
};

const sizeStyles = {
    sm: "px-3 py-1.5 text-xs",
    md: "px-4 py-2 text-sm",
    lg: "px-5 py-2.5 text-sm",
};

export default function Button({
    children,
    onClick,
    variant = "primary",
    size = "md",
    disabled = false,
    loading = false,
    className,
    type = "button",
}: ButtonProps) {
    return (
        <button
            type={type}
            onClick={onClick}
            disabled={disabled || loading}
            className={clsx(
                "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
                "focus:outline-none focus:ring-2 focus:ring-offset-1",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                variantStyles[variant],
                sizeStyles[size],
                className
            )}
        >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {children}
        </button>
    );
}
