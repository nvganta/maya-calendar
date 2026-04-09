import type {
  CalendarEvent,
  EventCreate,
  EventUpdate,
  Reminder,
  UserSettings,
  AuthUser,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// --- Auth ---

export async function validateSSO(
  ssoToken: string
): Promise<{ access_token: string; user: AuthUser }> {
  const res = await fetch(`${API_URL}/api/sso/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sso_token: ssoToken }),
  });
  return handleResponse(res);
}

// --- Events ---

export async function listEvents(
  start: string,
  end: string,
  category?: string
): Promise<CalendarEvent[]> {
  const params = new URLSearchParams({ start, end });
  if (category) params.set("category", category);
  const res = await fetch(`${API_URL}/api/events?${params}`, {
    headers: authHeaders(),
  });
  return handleResponse(res);
}

export async function createEvent(data: EventCreate): Promise<CalendarEvent> {
  const res = await fetch(`${API_URL}/api/events`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse(res);
}

export async function updateEvent(
  id: string,
  data: EventUpdate
): Promise<CalendarEvent> {
  const res = await fetch(`${API_URL}/api/events/${id}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse(res);
}

export async function deleteEvent(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/events/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return handleResponse(res);
}

// --- Reminders ---

export async function listReminders(): Promise<Reminder[]> {
  const res = await fetch(`${API_URL}/api/events/reminders/pending`, {
    headers: authHeaders(),
  });
  return handleResponse(res);
}

// --- User Settings ---

export async function getUserSettings(): Promise<UserSettings> {
  const res = await fetch(`${API_URL}/api/user`, {
    headers: authHeaders(),
  });
  return handleResponse(res);
}

export async function updateUserSettings(
  data: Partial<UserSettings>
): Promise<UserSettings> {
  const res = await fetch(`${API_URL}/api/user`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse(res);
}
