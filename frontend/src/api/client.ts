const API_BASE_URL =
    import.meta.env.VITE_API_URL || "http://localhost:8080/api/v1";

interface RequestOptions {
    method?: "GET" | "POST" | "PUT" | "DELETE";
    body?: unknown;
    params?: Record<string, string | number | undefined>;
    signal?: AbortSignal;
}

class ApiError extends Error {
    status: number;

    constructor(status: number, message: string) {
        super(message);
        this.name = "ApiError";
        this.status = status;
    }
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { method = "GET", body, params, signal } = options;

    let url = `${API_BASE_URL}${endpoint}`;

    if (params) {
        const searchParams = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined) searchParams.append(key, String(value));
        });
        const queryString = searchParams.toString();
        if (queryString) url += `?${queryString}`;
    }

    const headers: Record<string, string> = {
        "Content-Type": "application/json",
    };

    const response = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal,
    });

    if (!response.ok) {
        const errorBody = await response.text().catch(() => "Unknown error");
        throw new ApiError(response.status, errorBody);
    }

    return response.json() as Promise<T>;
}

export const api = {
    get: <T>(endpoint: string, params?: Record<string, string | number | undefined>) =>
        request<T>(endpoint, { params }),

    post: <T>(endpoint: string, body: unknown) =>
        request<T>(endpoint, { method: "POST", body }),
};

export { ApiError };
export default api;
