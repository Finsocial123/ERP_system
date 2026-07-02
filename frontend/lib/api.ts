import type { AuthResponse } from "@/types";
import { clearCachedBranding } from "@/lib/branding";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
const TOKEN_KEY = "erp_access_token";
const AUTH_KEY = "erp_auth";
const ACADEMIC_SESSION_KEY = "erp_selected_academic_session_id";

type TokenRefreshResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

/** Fired when the saved auth user data is updated (e.g. after profile photo upload) */
export const AUTH_PROFILE_UPDATED_EVENT = "erp_auth_profile_updated";
export const AUTH_TOKEN_REFRESHED_EVENT = "erp_auth_token_refreshed";
export const AUTH_LOGGED_OUT_EVENT = "erp_auth_logged_out";
export const ACADEMIC_SESSION_CHANGED_EVENT = "erp_academic_session_changed";
export const NOTIFICATIONS_UPDATED_EVENT = "erp_notifications_updated";

let refreshPromise: Promise<string | null> | null = null;

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
  if (typeof window === "undefined") return;
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

function saveAccessToken(accessToken: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, accessToken);
  const saved = getSavedAuth();
  if (saved) {
    const updated: AuthResponse = { ...saved, access_token: accessToken };
    localStorage.setItem(AUTH_KEY, JSON.stringify(updated));
    window.dispatchEvent(new CustomEvent(AUTH_TOKEN_REFRESHED_EVENT, { detail: updated }));
  }
}

/**
 * Patch the persisted auth user object with new fields (e.g. photo_url after
 * a profile picture upload) and broadcast an event so AppShell re-reads it.
 */
export function updateSavedAuthUser(patch: Partial<AuthResponse["user"]>) {
  const saved = getSavedAuth();
  if (!saved || typeof window === "undefined") return;
  const updated: AuthResponse = { ...saved, user: { ...saved.user, ...patch } };
  localStorage.setItem(AUTH_KEY, JSON.stringify(updated));
  window.dispatchEvent(new CustomEvent(AUTH_PROFILE_UPDATED_EVENT, { detail: updated }));
}

export function clearAuth() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(ACADEMIC_SESSION_KEY);
  clearCachedBranding();
  window.dispatchEvent(new Event(AUTH_LOGGED_OUT_EVENT));
}

export async function logoutUser() {
  try {
    await fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    // Local auth is still cleared below even if the network request fails.
  } finally {
    clearAuth();
  }
}

export function dashboardPathForRole(role?: string, mustChangePassword = false) {
  if (mustChangePassword) return "/change-password";
  if (role === "TEACHER") return "/teacher-dashboard";
  if (role === "STUDENT") return "/student-dashboard";
  if (role === "PARENT") return "/parent-dashboard";
  return "/dashboard";
}

function normalizeApiPath(input: string) {
  if (input.startsWith(API_BASE)) return input.slice(API_BASE.length);
  return input;
}

function shouldAttemptRefresh(input: string) {
  if (typeof window === "undefined" || !getToken()) return false;
  const path = normalizeApiPath(input);
  return !(
    path.startsWith("/auth/login") ||
    path.startsWith("/auth/refresh") ||
    path.startsWith("/auth/logout") ||
    path.startsWith("/auth/register-school") ||
    path.startsWith("/auth/verify-school-registration") ||
    path.startsWith("/auth/forgot-password") ||
    path.startsWith("/auth/reset-password")
  );
}

export async function refreshAccessToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) return null;
      const data = (await res.json()) as TokenRefreshResponse;
      if (!data.access_token) return null;
      saveAccessToken(data.access_token);
      return data.access_token;
    } catch {
      return null;
    }
  })().finally(() => {
    refreshPromise = null;
  });

  return refreshPromise;
}

function buildUrl(path: string) {
  return path.startsWith("http://") || path.startsWith("https://") ? path : `${API_BASE}${path}`;
}

function shouldRefreshNotificationsAfterWrite(path: string) {
  const normalizedPath = normalizeApiPath(path).split("?")[0];

  // Only refresh the global bell for modules that can create/update in-app notifications.
  // This avoids refreshing notification count after unrelated writes like student status, fee form edits, etc.
  return (
    normalizedPath.startsWith("/communication") ||
    normalizedPath.startsWith("/homework") ||
    normalizedPath.startsWith("/assignments") ||
    normalizedPath.startsWith("/exams") ||
    normalizedPath.startsWith("/meetings") ||
    normalizedPath.startsWith("/notice") ||
    normalizedPath.startsWith("/courses") ||
    normalizedPath.startsWith("/lessons") ||
    normalizedPath.startsWith("/attendance")
  );
}

function dispatchNotificationRefreshIfNeeded(path: string, method: string) {
  if (typeof window === "undefined" || method === "GET") return;
  if (shouldRefreshNotificationsAfterWrite(path)) {
    window.dispatchEvent(new Event(NOTIFICATIONS_UPDATED_EVENT));
  }
}

async function doFetchWithAuth(path: string, options: RequestInit, tokenOverride?: string | null) {
  const token = tokenOverride ?? getToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const selectedSessionId = getSelectedAcademicSessionId();
  if (selectedSessionId) headers.set("X-Academic-Session-Id", selectedSessionId);

  return fetch(buildUrl(path), {
    ...options,
    headers,
    credentials: options.credentials ?? "include",
  });
}

export async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  let res = await doFetchWithAuth(path, options);

  if (res.status === 401 && shouldAttemptRefresh(path)) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      res = await doFetchWithAuth(path, options, newToken);
    } else {
      clearAuth();
    }
  }

  return res;
}

async function parseResponseBody(res: Response) {
  const contentType = res.headers.get("content-type") || "";
  return contentType.includes("application/json") ? await res.json() : await res.text();
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const res = await authFetch(path, {
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

  const data = await parseResponseBody(res);

  if (!res.ok) {
    const message = typeof data === "object" && data?.detail ? data.detail : "Request failed";
    throw new Error(Array.isArray(message) ? message.map((m) => m.msg).join(", ") : message);
  }

  const method = (options.method || "GET").toUpperCase();
  dispatchNotificationRefreshIfNeeded(path, method);

  return data as T;
}

export type UploadProgressInfo = {
  loaded: number;
  total: number;
  percent: number;
};

type ApiUploadOptions = RequestInit & {
  onUploadProgress?: (progress: UploadProgressInfo) => void;
};

function parseXhrBody(xhr: XMLHttpRequest) {
  const contentType = xhr.getResponseHeader("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      return xhr.responseText ? JSON.parse(xhr.responseText) : null;
    } catch {
      return xhr.responseText;
    }
  }
  return xhr.responseText;
}

function xhrUpload<T>(path: string, formData: FormData, options: ApiUploadOptions, tokenOverride?: string | null): Promise<T> {
  const { onUploadProgress, headers: optionHeaders, method = "POST" } = options;

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(String(method).toUpperCase(), buildUrl(path), true);
    xhr.withCredentials = true;

    const token = tokenOverride ?? getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    const selectedSessionId = getSelectedAcademicSessionId();
    if (selectedSessionId) xhr.setRequestHeader("X-Academic-Session-Id", selectedSessionId);

    const headers = new Headers(optionHeaders);
    headers.forEach((value, key) => {
      if (key.toLowerCase() !== "content-type") xhr.setRequestHeader(key, value);
    });

    xhr.upload.onprogress = (event) => {
      if (!onUploadProgress || !event.lengthComputable) return;
      const percent = Math.max(0, Math.min(100, Math.round((event.loaded / event.total) * 100)));
      onUploadProgress({ loaded: event.loaded, total: event.total, percent });
    };

    xhr.onload = async () => {
      const data = parseXhrBody(xhr);

      if (xhr.status === 401 && shouldAttemptRefresh(path) && !tokenOverride) {
        const newToken = await refreshAccessToken();
        if (newToken) {
          try {
            resolve(await xhrUpload<T>(path, formData, options, newToken));
          } catch (err) {
            reject(err);
          }
          return;
        }
        clearAuth();
      }

      if (xhr.status < 200 || xhr.status >= 300) {
        const detail = typeof data === "object" && data?.detail ? data.detail : "Request failed";
        reject(new Error(Array.isArray(detail) ? detail.map((m) => m.msg).join(", ") : detail));
        return;
      }

      dispatchNotificationRefreshIfNeeded(path, String(method).toUpperCase());

      resolve(data as T);
    };

    xhr.onerror = () => {
      reject(new Error("Upload failed. Please check file size, internet connection, and server upload limit."));
    };

    xhr.onabort = () => reject(new Error("Upload cancelled"));
    xhr.ontimeout = () => reject(new Error("Upload timed out. Try compressing the video or uploading with a faster connection."));

    xhr.send(formData);
  });
}

export async function apiUpload<T>(path: string, formData: FormData, options: ApiUploadOptions = {}): Promise<T> {
  const { onUploadProgress, ...fetchOptions } = options;

  if (onUploadProgress && typeof window !== "undefined" && typeof XMLHttpRequest !== "undefined") {
    return xhrUpload<T>(path, formData, options);
  }

  const res = await authFetch(path, {
    ...fetchOptions,
    body: formData,
  });

  const data = await parseResponseBody(res);

  if (!res.ok) {
    const message = typeof data === "object" && data?.detail ? data.detail : "Request failed";
    throw new Error(Array.isArray(message) ? message.map((m) => m.msg).join(", ") : message);
  }

  const method = (fetchOptions.method || "POST").toUpperCase();
  dispatchNotificationRefreshIfNeeded(path, method);

  return data as T;
}

export function fileUrl(path?: string | null) {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_BASE}${path}`;
}
