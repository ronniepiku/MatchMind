import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Import after mocking
const { default: api, ApiError } = await import("@/api/client");
type ApiErrorType = InstanceType<typeof ApiError>;

describe("API Client", () => {
    beforeEach(() => {
        mockFetch.mockReset();
    });

    it("makes GET requests to the correct URL", async () => {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({ data: "test" }),
        });

        await api.get("/health");

        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining("/health"),
            expect.objectContaining({ method: "GET" }),
        );
    });

    it("appends query params to GET requests", async () => {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve([]),
        });

        await api.get("/players", { team_id: 1, season_id: 106 });

        const calledUrl = mockFetch.mock.calls[0][0] as string;
        expect(calledUrl).toContain("team_id=1");
        expect(calledUrl).toContain("season_id=106");
    });

    it("sends JSON body on POST requests", async () => {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({ xg: 0.5 }),
        });

        const body = { location_x: 108, location_y: 40 };
        await api.post("/xg/predict", body);

        const calledOptions = mockFetch.mock.calls[0][1];
        expect(calledOptions.method).toBe("POST");
        expect(calledOptions.body).toBe(JSON.stringify(body));
    });

    it("throws ApiError on 4xx responses", async () => {
        mockFetch.mockResolvedValueOnce({
            ok: false,
            status: 404,
            json: () => Promise.resolve({ detail: "Not found" }),
        });

        await expect(api.get("/nonexistent")).rejects.toThrow(ApiError);
        await expect(api.get("/nonexistent")).rejects.toThrow();
    });

    it("sanitizes 5xx error messages", async () => {
        mockFetch.mockResolvedValueOnce({
            ok: false,
            status: 500,
            json: () => Promise.resolve({ detail: "Internal DB error: connection pool exhausted" }),
        });

        try {
            await api.get("/broken");
        } catch (e) {
            expect(e).toBeInstanceOf(ApiError);
            expect((e as ApiErrorType).message).toBe("Server error. Please try again later.");
            expect((e as ApiErrorType).message).not.toContain("DB error");
        }
    });

    it("skips undefined params", async () => {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve([]),
        });

        await api.get("/test", { defined: "yes", missing: undefined });

        const calledUrl = mockFetch.mock.calls[0][0] as string;
        expect(calledUrl).toContain("defined=yes");
        expect(calledUrl).not.toContain("missing");
    });
});
