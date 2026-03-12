import type { DashboardData, Product, StockoutPrediction, Alert } from "@/types";

const API = "";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem("auth");
    if (stored) return JSON.parse(stored).token;
  } catch {}
  return null;
}

async function fetchJSON<T>(url: string, opts?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(opts?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API}${url}`, {
    ...opts,
    headers,
    cache: "no-store",
  });

  if (res.status === 401) {
    // Token expired — clear auth and reload
    if (typeof window !== "undefined") {
      localStorage.removeItem("auth");
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function fetchDashboard(): Promise<DashboardData> {
  return fetchJSON("/api/dashboard");
}

export async function fetchInventory(): Promise<{ products: Product[]; count: number }> {
  return fetchJSON("/api/inventory");
}

export async function fetchPredictions(): Promise<{ predictions: StockoutPrediction[]; count: number }> {
  return fetchJSON("/api/predictions");
}

export async function fetchAlerts(
  type?: string,
  isRead?: boolean
): Promise<{ alerts: Alert[]; count: number }> {
  const params = new URLSearchParams();
  if (type) params.set("type", type);
  if (isRead !== undefined) params.set("is_read", String(isRead));
  const qs = params.toString();
  return fetchJSON(`/api/alerts${qs ? `?${qs}` : ""}`);
}

export async function markAlertRead(id: number): Promise<void> {
  await fetchJSON(`/api/alerts/${id}/read`, { method: "PATCH" });
}

export async function refreshPredictions(): Promise<{ status: string }> {
  return fetchJSON("/api/predictions/refresh", { method: "POST" });
}

export async function seedDemoData(): Promise<{ status: string }> {
  return fetchJSON("/api/auth/seed-demo", { method: "POST" });
}

export async function squareSync(): Promise<any> {
  return fetchJSON("/api/square/sync", { method: "POST" });
}

export async function getSquareAuthUrl(): Promise<{ url: string }> {
  return fetchJSON("/api/auth/square/authorize");
}

export async function disconnectSquare(): Promise<any> {
  return fetchJSON("/api/auth/square/disconnect", { method: "POST" });
}

export async function getSquareLocations(): Promise<{ locations: any[] }> {
  return fetchJSON("/api/auth/square/locations");
}

export async function setSquareLocation(locationId: string): Promise<any> {
  return fetchJSON(`/api/auth/square/set-location?location_id=${locationId}`, { method: "POST" });
}
