import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("[ErrorBoundary] Caught error:", error, errorInfo);
    }

    private handleReset = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <div className="flex flex-col items-center justify-center gap-4 py-16">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-danger-500/10">
                        <AlertTriangle className="h-6 w-6 text-danger-500" />
                    </div>
                    <div className="text-center">
                        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                            Something went wrong
                        </h3>
                        <p className="mt-1 text-sm text-[var(--text-muted)]">
                            This section encountered an unexpected error.
                        </p>
                    </div>
                    <button
                        onClick={this.handleReset}
                        className="rounded-md bg-[var(--bg-tertiary)] px-3 py-1.5 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-quaternary)] transition-colors"
                    >
                        Try Again
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
