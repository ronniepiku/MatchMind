import { clsx } from "clsx";

interface BadgeProps {
    children: React.ReactNode;
    variant?: "default" | "success" | "warning" | "danger" | "info";
    size?: "sm" | "md";
}

const variantStyles = {
    default: "bg-surface-200 text-surface-700 dark:bg-surface-700 dark:text-surface-300",
    success: "bg-success-500/10 text-success-500",
    warning: "bg-warning-500/10 text-warning-500",
    danger: "bg-danger-500/10 text-danger-500",
    info: "bg-accent-500/10 text-accent-500",
};

export default function Badge({ children, variant = "default", size = "sm" }: BadgeProps) {
    return (
        <span
            className={clsx(
                "inline-flex items-center rounded-full font-medium",
                size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs",
                variantStyles[variant]
            )}
        >
            {children}
        </span>
    );
}
