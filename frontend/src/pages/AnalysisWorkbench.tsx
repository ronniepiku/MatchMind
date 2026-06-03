import { useState, useEffect, useCallback } from "react";
import { Card, Button, ErrorState } from "@/components/shared";
import { api } from "@/api";
import type { QueryDefinition, QueryListResponse, QueryResult } from "@/api/types";

export default function AnalysisWorkbench() {
    const [queries, setQueries] = useState<QueryDefinition[]>([]);
    const [categories, setCategories] = useState<string[]>([]);
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
    const [selectedQuery, setSelectedQuery] = useState<QueryDefinition | null>(null);
    const [params, setParams] = useState<Record<string, string>>({});
    const [result, setResult] = useState<QueryResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchQueries = useCallback(async () => {
        try {
            const data = await api.get<QueryListResponse>("/analysis/queries");
            setQueries(data.queries);
            setCategories(data.categories);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Failed to load queries");
        }
    }, []);

    useEffect(() => {
        fetchQueries();
    }, [fetchQueries]);

    const handleSelectQuery = (query: QueryDefinition) => {
        setSelectedQuery(query);
        setResult(null);
        setError(null);
        const defaults: Record<string, string> = {};
        query.parameters.forEach((p) => {
            if (p.default !== null && p.default !== undefined) {
                defaults[p.name] = String(p.default);
            }
        });
        setParams(defaults);
    };

    const handleExecute = async () => {
        if (!selectedQuery) return;
        setLoading(true);
        setError(null);
        try {
            const typedParams: Record<string, unknown> = {};
            selectedQuery.parameters.forEach((p) => {
                const val = params[p.name];
                if (val === undefined || val === "") {
                    if (!p.required) typedParams[p.name] = null;
                    return;
                }
                if (p.type === "int") typedParams[p.name] = Number(val);
                else if (p.type === "float") typedParams[p.name] = parseFloat(val);
                else typedParams[p.name] = val;
            });

            const data = await api.post<QueryResult>("/analysis/query", {
                query_id: selectedQuery.query_id,
                parameters: typedParams,
            });
            setResult(data);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Query execution failed");
        } finally {
            setLoading(false);
        }
    };

    const filteredQueries = selectedCategory
        ? queries.filter((q) => q.category === selectedCategory)
        : queries;

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                    Analysis Workbench
                </h1>
                <p className="text-sm text-[var(--text-muted)]">
                    Parameterised queries for ad-hoc football analysis
                </p>
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                {/* Query Selector */}
                <div className="space-y-4">
                    {/* Category filter */}
                    <Card>
                        <h3 className="mb-2 text-sm font-semibold text-[var(--text-primary)]">
                            Categories
                        </h3>
                        <div className="flex flex-wrap gap-1">
                            <button
                                onClick={() => setSelectedCategory(null)}
                                className={`rounded-full px-2 py-1 text-xs font-medium transition-colors ${!selectedCategory
                                    ? "bg-accent-500 text-white"
                                    : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                                    }`}
                            >
                                All
                            </button>
                            {categories.map((cat) => (
                                <button
                                    key={cat}
                                    onClick={() => setSelectedCategory(cat)}
                                    className={`rounded-full px-2 py-1 text-xs font-medium transition-colors ${selectedCategory === cat
                                        ? "bg-accent-500 text-white"
                                        : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                                        }`}
                                >
                                    {cat}
                                </button>
                            ))}
                        </div>
                    </Card>

                    {/* Query list */}
                    <Card>
                        <h3 className="mb-2 text-sm font-semibold text-[var(--text-primary)]">
                            Queries ({filteredQueries.length})
                        </h3>
                        <div className="max-h-96 space-y-1 overflow-y-auto">
                            {filteredQueries.map((q) => (
                                <button
                                    key={q.query_id}
                                    onClick={() => handleSelectQuery(q)}
                                    className={`w-full rounded-lg p-2 text-left transition-colors ${selectedQuery?.query_id === q.query_id
                                        ? "bg-accent-500/10 border border-accent-500/30"
                                        : "hover:bg-[var(--bg-secondary)]"
                                        }`}
                                >
                                    <div className="text-sm font-medium text-[var(--text-primary)]">
                                        {q.name}
                                    </div>
                                    <div className="mt-0.5 text-xs text-[var(--text-muted)] line-clamp-2">
                                        {q.description}
                                    </div>
                                </button>
                            ))}
                        </div>
                    </Card>
                </div>

                {/* Parameter Form + Results */}
                <div className="space-y-4 lg:col-span-2">
                    {selectedQuery ? (
                        <>
                            {/* Query info */}
                            <Card>
                                <div className="flex items-start justify-between">
                                    <div>
                                        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                                            {selectedQuery.name}
                                        </h2>
                                        <p className="mt-1 text-sm text-[var(--text-secondary)]">
                                            {selectedQuery.description}
                                        </p>
                                        <span className="mt-2 inline-block rounded-full bg-[var(--bg-secondary)] px-2 py-0.5 text-xs text-[var(--text-muted)]">
                                            {selectedQuery.category}
                                        </span>
                                    </div>
                                </div>

                                {/* Parameters */}
                                <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                                    {selectedQuery.parameters.map((p) => (
                                        <div key={p.name}>
                                            <label className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
                                                {p.name}
                                                {p.required && <span className="text-red-500"> *</span>}
                                            </label>
                                            <input
                                                type={p.type === "int" || p.type === "float" ? "number" : "text"}
                                                value={params[p.name] || ""}
                                                onChange={(e) =>
                                                    setParams({ ...params, [p.name]: e.target.value })
                                                }
                                                placeholder={p.description}
                                                className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-sm"
                                            />
                                        </div>
                                    ))}
                                </div>

                                <div className="mt-4 flex gap-2">
                                    <Button onClick={handleExecute} disabled={loading}>
                                        {loading ? "Executing..." : "Run Query"}
                                    </Button>
                                </div>
                            </Card>

                            {error && <ErrorState message={error} />}

                            {/* Results */}
                            {result && (
                                <Card>
                                    <div className="mb-3 flex items-center justify-between">
                                        <h3 className="font-semibold text-[var(--text-primary)]">
                                            Results ({result.row_count} rows)
                                        </h3>
                                        <button
                                            onClick={() => {
                                                const csv = [
                                                    Object.keys(result.results[0] || {}).join(","),
                                                    ...result.results.map((r) => Object.values(r).join(",")),
                                                ].join("\n");
                                                const blob = new Blob([csv], { type: "text/csv" });
                                                const url = URL.createObjectURL(blob);
                                                const a = document.createElement("a");
                                                a.href = url;
                                                a.download = `${selectedQuery.query_id}_results.csv`;
                                                a.click();
                                            }}
                                            className="rounded-lg bg-[var(--bg-secondary)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                                        >
                                            Export CSV
                                        </button>
                                    </div>

                                    {result.row_count === 0 ? (
                                        <p className="text-sm text-[var(--text-muted)]">
                                            No results found for the given parameters.
                                        </p>
                                    ) : (
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-sm">
                                                <thead>
                                                    <tr className="border-b border-[var(--border-color)]">
                                                        {Object.keys(result.results[0]).map((col) => (
                                                            <th
                                                                key={col}
                                                                className="pb-2 pr-4 text-left text-xs font-medium text-[var(--text-muted)]"
                                                            >
                                                                {col.replace(/_/g, " ")}
                                                            </th>
                                                        ))}
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {result.results.slice(0, 50).map((row, i) => (
                                                        <tr key={i} className="border-b border-[var(--border-color)]/30">
                                                            {Object.values(row).map((val, j) => (
                                                                <td key={j} className="py-1.5 pr-4 text-[var(--text-secondary)]">
                                                                    {val === null ? "—" : typeof val === "number" ? val.toLocaleString() : String(val)}
                                                                </td>
                                                            ))}
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                            {result.row_count > 50 && (
                                                <p className="mt-2 text-xs text-[var(--text-muted)]">
                                                    Showing first 50 of {result.row_count} rows. Export for full data.
                                                </p>
                                            )}
                                        </div>
                                    )}
                                </Card>
                            )}
                        </>
                    ) : (
                        <Card>
                            <div className="py-12 text-center text-[var(--text-muted)]">
                                <p className="text-lg">Select a query from the left panel</p>
                                <p className="mt-1 text-sm">
                                    Choose a category and query to begin your analysis
                                </p>
                            </div>
                        </Card>
                    )}
                </div>
            </div>
        </div>
    );
}
