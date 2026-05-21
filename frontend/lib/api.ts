import type { AuthResponse } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
const TOKEN_KEY = "erp_access_token";
const AUTH_KEY = "erp_auth";

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
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

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(AUTH_KEY);
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

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
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
