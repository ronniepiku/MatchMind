import { clsx } from "clsx";
import { Loader2 } from "lucide-react";

interface LoadingProps {
    message?: string;
    className?: string;
    size?: "sm" | "md" | "lg";
}

export default function Loading({
    message = "Loading...",
    className,
    size = "md",
}: LoadingProps) {
    const sizeMap = { sm: "h-4 w-4", md: "h-6 w-6", lg: "h-8 w-8" };

    return (
        <div
            className={clsx(
                "flex flex-col items-center justify-center gap-3 py-12",
                className
            )}
        >
            <Loader2 className={clsx(sizeMap[size], "animate-spin text-accent-500")} />
            <p className="text-sm text-[var(--text-muted)]">{message}</p>
        </div>
    );
}
