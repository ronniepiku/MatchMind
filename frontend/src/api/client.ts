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
        // Parse structured error response; never expose raw server details
        let message = "Request failed";
        try {
            const errorData = await response.json();
            if (errorData.detail && typeof errorData.detail === "string") {
                // Only use server message for client errors (4xx), sanitize 5xx
                message = response.status >= 500
                    ? "Server error. Please try again later."
                    : errorData.detail;
            }
        } catch {
            if (response.status >= 500) {
                message = "Server error. Please try again later.";
            }
        }
        throw new ApiError(response.status, message);
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
