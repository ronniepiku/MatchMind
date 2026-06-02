import { AlertTriangle } from "lucide-react";
import Button from "./Button";

interface ErrorStateProps {
    title?: string;
    message?: string;
    onRetry?: () => void;
}

export default function ErrorState({
    title = "Something went wrong",
    message = "Failed to load data. Please try again.",
    onRetry,
}: ErrorStateProps) {
    return (
        <div className="flex flex-col items-center justify-center gap-4 py-16">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-danger-500/10">
                <AlertTriangle className="h-6 w-6 text-danger-500" />
            </div>
            <div className="text-center">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
                <p className="mt-1 text-sm text-[var(--text-muted)]">{message}</p>
            </div>
            {onRetry && (
                <Button variant="secondary" size="sm" onClick={onRetry}>
                    Try Again
                </Button>
            )}
        </div>
    );
}
