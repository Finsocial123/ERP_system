import type { AuthResponse } from "@/types";
import { clearCachedBranding } from "@/lib/branding";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
const TOKEN_KEY = "erp_access_token";
const AUTH_KEY = "erp_auth";
const ACADEMIC_SESSION_KEY = "erp_selected_academic_session_id";

/** Fired when the saved auth user data is updated (e.g. after profile photo upload) */
export const AUTH_PROFILE_UPDATED_EVENT = "erp_auth_profile_updated";
export const ACADEMIC_SESSION_CHANGED_EVENT = "erp_academic_session_changed";

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}


export function getSelectedAcademicSessionId() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACADEMIC_SESSION_KEY);
}

export function setSelectedAcademicSessionId(sessionId: number | string | null) {
  if (typeof window === "undefined") return;
  if (sessionId === null || sessionId === "") {
    localStorage.removeItem(ACADEMIC_SESSION_KEY);
  } else {
    localStorage.setItem(ACADEMIC_SESSION_KEY, String(sessionId));
  }
  window.dispatchEvent(new CustomEvent(ACADEMIC_SESSION_CHANGED_EVENT, { detail: sessionId ? String(sessionId) : null }));
}

export function saveAuth(auth: AuthResponse) {
  localStorage.setItem(TOKEN_KEY, auth.access_token);
  localStorage.setItem(AUTH_KEY, JSON.stringify(auth));
}

export function getSavedAuth(): AuthResponse | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(AUTH_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthResponse;
  } catch {
    return null;
  }
}

/**
 * Patch the persisted auth user object with new fields (e.g. photo_url after
 * a profile picture upload) and broadcast an event so AppShell re-reads it.
 */
export function updateSavedAuthUser(patch: Partial<AuthResponse["user"]>) {
  const saved = getSavedAuth();
  if (!saved) return;
  const updated: AuthResponse = { ...saved, user: { ...saved.user, ...patch } };
  localStorage.setItem(AUTH_KEY, JSON.stringify(updated));
  window.dispatchEvent(new CustomEvent(AUTH_PROFILE_UPDATED_EVENT, { detail: updated }));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(ACADEMIC_SESSION_KEY);
  clearCachedBranding();
}

export function dashboardPathForRole(role?: string, mustChangePassword = false) {
  if (mustChangePassword) return "/change-password";
  if (role === "TEACHER") return "/teacher-dashboard";
  if (role === "STUDENT") return "/student-dashboard";
  if (role === "PARENT") return "/parent-dashboard";
  return "/dashboard";
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const selectedSessionId = getSelectedAcademicSessionId();
  if (selectedSessionId) headers.set("X-Academic-Session-Id", selectedSessionId);

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  // Handle 204 No Content responses (e.g., DELETE operations)
  if (res.status === 204) {
    if (!res.ok) {
      throw new Error("Request failed");
    }
    return undefined as T;
  }

  const contentType = res.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await res.json() : await res.text();

  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined") clearAuth();
    const message = typeof data === "object" && data?.detail ? data.detail : "Request failed";
    throw new Error(Array.isArray(message) ? message.map((m) => m.msg).join(", ") : message);
  }

  return data as T;
}


export async function apiUpload<T>(path: string, formData: FormData, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const selectedSessionId = getSelectedAcademicSessionId();
  if (selectedSessionId) headers.set("X-Academic-Session-Id", selectedSessionId);

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    body: formData,
    headers,
  });

  const contentType = res.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await res.json() : await res.text();

  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined") clearAuth();
    const message = typeof data === "object" && data?.detail ? data.detail : "Request failed";
    throw new Error(Array.isArray(message) ? message.map((m) => m.msg).join(", ") : message);
  }

  return data as T;
}

export function fileUrl(path?: string | null) {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_BASE}${path}`;
}
