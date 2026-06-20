const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Method = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";

interface RequestOptions {
  body?: unknown;
  params?: Record<string, string | number | boolean>;
  token?: string; // explicit token override — used immediately after login before store is hydrated
}

class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(`API error ${status}`);
  }
}

function buildUrl(path: string, params?: Record<string, string | number | boolean>): string {
  const url = new URL(path, API_BASE);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

async function request<T>(
  method: Method,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  // Explicit token takes priority (e.g. immediately after login before store persists to localStorage)
  let token: string | null = options.token ?? null;
  if (!token && typeof window !== "undefined") {
    try {
      const raw = localStorage.getItem("auth-store");
      if (raw) {
        const parsed = JSON.parse(raw) as { state?: { token?: string } };
        token = parsed.state?.token ?? null;
      }
    } catch {
      // ignore parse errors
    }
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(buildUrl(path, options.params), {
    method,
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (res.status === 401) {
    // Clear stale token and redirect — avoids hard import cycle with store
    if (typeof window !== "undefined") {
      localStorage.removeItem("auth-store");
      window.location.href = "/login";
    }
  }

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ message: res.statusText }));
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | boolean>, token?: string) =>
    request<T>("GET", path, { params, token }),

  post: <T>(path: string, body?: unknown) => request<T>("POST", path, { body }),

  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, { body }),

  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, { body }),

  delete: <T>(path: string) => request<T>("DELETE", path),

  createShareLink: (tripId: string) =>
    request<TripOut>("POST", `/api/v1/trips/${tripId}/share`),

  getSharedTrip: (token: string) =>
    request<ShareTripOut>("GET", `/api/v1/share/${token}`),

  updateTrip: (tripId: string, body: Partial<TripUpdate>) =>
    request<TripOut>("PUT", `/api/v1/trips/${tripId}`, { body }),

  deleteTrip: (tripId: string) =>
    request<void>("DELETE", `/api/v1/trips/${tripId}`),

  selectHotel: (tripId: string, hotelId: string) =>
    request<HotelCandidateOut[]>("POST", `/api/v1/trips/${tripId}/hotels/${hotelId}/select`),

  /** Fetches the .ics blob with auth and triggers a browser download. */
  downloadCalendarIcs: async (tripId: string, cityName: string): Promise<void> => {
    let token: string | null = null;
    try {
      const raw = localStorage.getItem("auth-store");
      if (raw) {
        const parsed = JSON.parse(raw) as { state?: { token?: string } };
        token = parsed.state?.token ?? null;
      }
    } catch { /* ignore */ }

    const res = await fetch(buildUrl(`/api/v1/trips/${tripId}/calendar.ics`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error("Failed to download calendar");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `travelos-${cityName.toLowerCase().replace(/\s+/g, "-")}.ics`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
};

export { ApiError };

// ── typed response shapes ─────────────────────────────────────────────────────

export interface UserOut {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface PreferenceOut {
  id: string;
  user_id: string;
  pace: string | null;
  luxury_tier: string | null;
  walking_tolerance: string | null;
  food_prefs: string[] | null;
  interests: string[] | null;
  budget_behavior: string | null;
  updated_at: string;
}

export interface TripOut {
  id: string;
  title: string;
  destination_city: string;
  destination_country: string | null;
  latitude: number | null;
  longitude: number | null;
  start_date: string;
  end_date: string;
  num_travelers: number;
  budget_total: number | null;
  budget_currency: string;
  status: string;
  packing_list: { categories: Record<string, string[]>; destination_specific?: string[] } | null;
  cover_image_url: string | null;
  share_token: string | null;
  share_expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TripUpdate {
  title?: string;
  destination_city?: string;
  destination_country?: string | null;
  start_date?: string;
  end_date?: string;
  num_travelers?: number;
  budget_total?: number | null;
  budget_currency?: string;
}

export interface ShareTripOut {
  id: string;
  title: string;
  destination_city: string;
  destination_country: string | null;
  start_date: string;
  end_date: string;
  num_travelers: number;
  budget_currency: string;
  cover_image_url: string | null;
  packing_list: { categories: Record<string, string[]>; destination_specific?: string[] } | null;
  itinerary: ItineraryItemOut[];
}

export interface ApprovalOut {
  id: string;
  trip_id: string;
  proposed_by: string;
  change_type: string;
  summary: string;
  payload: Record<string, unknown>;
  status: string;
  created_at: string;
  resolved_at: string | null;
}

export interface ChatSource {
  type: string;
  name: string;
  lat?: number;
  lng?: number;
  [key: string]: unknown;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  proposal_id?: string | null;
}

export interface HotelCandidateOut {
  id: string;
  trip_id: string;
  provider: string;
  provider_hotel_id: string;
  name: string;
  star_rating: number | null;
  latitude: number | null;
  longitude: number | null;
  address: string | null;
  image_url: string | null;
  price_total: number | null;
  price_currency: string | null;
  price_per_night: number | null;
  meal_plan: string | null;
  refundable: boolean | null;
  match_score: number | null;
  is_selected: boolean;
  created_at: string;
}

export interface WeatherDay {
  date: string;
  temp_min_c: number;
  temp_max_c: number;
  precipitation_mm: number;
  precipitation_prob: number;
  condition_code: number;
  condition_label: string;
  is_adverse: boolean;
  is_climate_normal: boolean;
}

export interface ItineraryItemOut {
  id: string;
  trip_id: string;
  day_number: number;
  item_date: string;
  start_time: string | null;
  end_time: string | null;
  item_type: string;
  title: string;
  description: string | null;
  latitude: number | null;
  longitude: number | null;
  address: string | null;
  source_provider: string | null;
  source_ref: string | null;
  est_cost: number | null;
  est_cost_currency: string | null;
  is_outdoor: boolean;
  sort_order: number;
  conflict_warning: string | null;
}
