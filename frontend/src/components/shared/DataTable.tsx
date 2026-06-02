import { clsx } from "clsx";
import { useState, useMemo } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

interface Column<T> {
    key: keyof T & string;
    label: string;
    sortable?: boolean;
    align?: "left" | "center" | "right";
    width?: string;
    render?: (row: T) => React.ReactNode;
    format?: (value: unknown) => string;
}

interface DataTableProps<T extends object> {
    columns: Column<T>[];
    data: T[];
    className?: string;
    compact?: boolean;
    striped?: boolean;
    highlightRow?: (row: T) => boolean;
    onRowClick?: (row: T) => void;
    emptyMessage?: string;
}

type SortDirection = "asc" | "desc" | null;

export default function DataTable<T extends object>({
    columns,
    data,
    className,
    compact = false,
    striped = true,
    highlightRow,
    onRowClick,
    emptyMessage = "No data available",
}: DataTableProps<T>) {
    const [sortKey, setSortKey] = useState<string | null>(null);
    const [sortDirection, setSortDirection] = useState<SortDirection>(null);

    const handleSort = (key: string) => {
        if (sortKey === key) {
            if (sortDirection === "asc") setSortDirection("desc");
            else if (sortDirection === "desc") {
                setSortKey(null);
                setSortDirection(null);
            }
        } else {
            setSortKey(key);
            setSortDirection("asc");
        }
    };

    const sortedData = useMemo(() => {
        if (!sortKey || !sortDirection) return data;
        return [...data].sort((a, b) => {
            const aVal = (a as Record<string, unknown>)[sortKey];
            const bVal = (b as Record<string, unknown>)[sortKey];
            if (aVal == null && bVal == null) return 0;
            if (aVal == null) return 1;
            if (bVal == null) return -1;
            if (typeof aVal === "number" && typeof bVal === "number") {
                return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
            }
            const aStr = String(aVal);
            const bStr = String(bVal);
            return sortDirection === "asc"
                ? aStr.localeCompare(bStr)
                : bStr.localeCompare(aStr);
        });
    }, [data, sortKey, sortDirection]);

    if (data.length === 0) {
        return (
            <div className="flex items-center justify-center py-12 text-sm text-[var(--text-muted)]">
                {emptyMessage}
            </div>
        );
    }

    return (
        <div className={clsx("overflow-x-auto", className)}>
            <table className="data-table w-full text-left">
                <thead>
                    <tr className="border-b border-[var(--border-color)]">
                        {columns.map((col) => (
                            <th
                                key={col.key}
                                style={col.width ? { width: col.width } : undefined}
                                className={clsx(
                                    "whitespace-nowrap px-3 font-medium text-[var(--text-muted)] uppercase tracking-wider",
                                    compact ? "py-2 text-[10px]" : "py-3 text-xs",
                                    col.align === "right" && "text-right",
                                    col.align === "center" && "text-center",
                                    col.sortable && "cursor-pointer select-none hover:text-[var(--text-primary)]"
                                )}
                                onClick={col.sortable ? () => handleSort(col.key) : undefined}
                            >
                                <span className="inline-flex items-center gap-1">
                                    {col.label}
                                    {col.sortable && (
                                        <span className="inline-flex">
                                            {sortKey === col.key ? (
                                                sortDirection === "asc" ? (
                                                    <ChevronUp className="h-3 w-3" />
                                                ) : (
                                                    <ChevronDown className="h-3 w-3" />
                                                )
                                            ) : (
                                                <ChevronsUpDown className="h-3 w-3 opacity-40" />
                                            )}
                                        </span>
                                    )}
                                </span>
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {sortedData.map((row, idx) => (
                        <tr
                            key={idx}
                            onClick={onRowClick ? () => onRowClick(row) : undefined}
                            className={clsx(
                                "border-b border-[var(--border-color)] last:border-0 transition-colors",
                                striped && idx % 2 === 1 && "bg-[var(--bg-secondary)]/50",
                                highlightRow?.(row) && "bg-accent-500/5",
                                onRowClick && "cursor-pointer hover:bg-[var(--bg-secondary)]"
                            )}
                        >
                            {columns.map((col) => (
                                <td
                                    key={col.key}
                                    className={clsx(
                                        "px-3 text-sm text-[var(--text-primary)]",
                                        compact ? "py-1.5" : "py-2.5",
                                        col.align === "right" && "text-right tabular-nums",
                                        col.align === "center" && "text-center"
                                    )}
                                >
                                    {col.render
                                        ? col.render(row)
                                        : col.format
                                            ? col.format((row as Record<string, unknown>)[col.key])
                                            : String((row as Record<string, unknown>)[col.key] ?? "-")}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export type { Column };
