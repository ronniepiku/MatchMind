/**
 * Formatting utilities for the analytics dashboard.
 */

export function formatNumber(value: number, decimals = 1): string {
    if (Number.isInteger(value) && decimals === 0) return value.toString();
    return value.toFixed(decimals);
}

export function formatPercentage(value: number, decimals = 1): string {
    return `${(value * 100).toFixed(decimals)}%`;
}

export function formatPer90(value: number): string {
    return value.toFixed(2);
}

export function formatMinutes(minutes: number): string {
    if (minutes >= 1000) return `${(minutes / 1000).toFixed(1)}k`;
    return minutes.toString();
}

export function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
    });
}

export function truncateName(name: string, maxLength = 18): string {
    if (name.length <= maxLength) return name;
    return name.slice(0, maxLength - 1) + "…";
}

export function getPercentileColor(percentile: number): string {
    if (percentile >= 90) return "var(--color-success-500)";
    if (percentile >= 75) return "var(--color-chart-2)";
    if (percentile >= 50) return "var(--color-chart-1)";
    if (percentile >= 25) return "var(--color-warning-500)";
    return "var(--color-danger-500)";
}

export function getChangeIndicator(value: number): "up" | "down" | "neutral" {
    if (value > 0.5) return "up";
    if (value < -0.5) return "down";
    return "neutral";
}
