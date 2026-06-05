import type { SchoolBranding, SchoolBrandingPublic } from "@/types";

export type BrandingLike = Partial<SchoolBranding | SchoolBrandingPublic> | null | undefined;

export const BRANDING_CACHE_KEY = "erp_school_branding_cache";
export const BRANDING_UPDATED_EVENT = "erp-branding-updated";

export const DEFAULT_BRANDING: Omit<SchoolBranding, "id" | "school_id"> = {
  logo_url: null,
  favicon_url: null,
  primary_color: "#2563eb",
  secondary_color: "#0f172a",
  accent_color: "#22c55e",
  sidebar_color: "#0f172a",
  background_color: "#f8fafc",
  text_color: "#0f172a",
  theme_mode: "light",
  theme_source: "preset",
  preset_name: "professional_blue",
  border_radius: 16,
};

export const BRANDING_PRESETS: Record<string, Omit<SchoolBranding, "id" | "school_id" | "logo_url" | "favicon_url">> = {
  professional_blue: {
    primary_color: "#2563eb",
    secondary_color: "#0f172a",
    accent_color: "#22c55e",
    sidebar_color: "#0f172a",
    background_color: "#f8fafc",
    text_color: "#0f172a",
    theme_mode: "light",
    theme_source: "preset",
    preset_name: "professional_blue",
    border_radius: 16,
  },
  modern_green: {
    primary_color: "#059669",
    secondary_color: "#064e3b",
    accent_color: "#14b8a6",
    sidebar_color: "#052e2b",
    background_color: "#f0fdf4",
    text_color: "#0f172a",
    theme_mode: "light",
    theme_source: "preset",
    preset_name: "modern_green",
    border_radius: 18,
  },
  premium_purple: {
    primary_color: "#7c3aed",
    secondary_color: "#2e1065",
    accent_color: "#f59e0b",
    sidebar_color: "#1e1b4b",
    background_color: "#faf5ff",
    text_color: "#111827",
    theme_mode: "light",
    theme_source: "preset",
    preset_name: "premium_purple",
    border_radius: 20,
  },
  classic_maroon: {
    primary_color: "#be123c",
    secondary_color: "#4c0519",
    accent_color: "#f59e0b",
    sidebar_color: "#1f1720",
    background_color: "#fff7ed",
    text_color: "#111827",
    theme_mode: "light",
    theme_source: "preset",
    preset_name: "classic_maroon",
    border_radius: 14,
  },
  minimal_slate: {
    primary_color: "#475569",
    secondary_color: "#0f172a",
    accent_color: "#0ea5e9",
    sidebar_color: "#020617",
    background_color: "#f8fafc",
    text_color: "#0f172a",
    theme_mode: "light",
    theme_source: "preset",
    preset_name: "minimal_slate",
    border_radius: 12,
  },
};

export function presetLabel(key: string) {
  return key
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function hexToRgb(hex: string) {
  const normalized = /^#[0-9a-f]{6}$/i.test(hex) ? hex : DEFAULT_BRANDING.primary_color;
  const value = normalized.slice(1);
  return {
    r: parseInt(value.slice(0, 2), 16),
    g: parseInt(value.slice(2, 4), 16),
    b: parseInt(value.slice(4, 6), 16),
  };
}

function rgbToHex(r: number, g: number, b: number) {
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v)));
  return `#${[clamp(r), clamp(g), clamp(b)]
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("")}`;
}

function mix(hex: string, target: "white" | "black", amount: number) {
  const { r, g, b } = hexToRgb(hex);
  const tr = target === "white" ? 255 : 0;
  const tg = target === "white" ? 255 : 0;
  const tb = target === "white" ? 255 : 0;
  return rgbToHex(r + (tr - r) * amount, g + (tg - g) * amount, b + (tb - b) * amount);
}

export function readableTextColor(background: string) {
  const { r, g, b } = hexToRgb(background);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.56 ? "#0f172a" : "#ffffff";
}

export function normalizeBranding(branding: BrandingLike) {
  return {
    ...DEFAULT_BRANDING,
    ...(branding || {}),
  };
}

export function buildLogoGeneratedTheme(primary: string, current?: BrandingLike): Omit<SchoolBranding, "id" | "school_id"> {
  const base = normalizeBranding(current);
  return {
    ...base,
    primary_color: primary,
    secondary_color: mix(primary, "black", 0.62),
    accent_color: mix(primary, "white", 0.28),
    sidebar_color: mix(primary, "black", 0.76),
    background_color: mix(primary, "white", 0.94),
    text_color: "#0f172a",
    theme_source: "logo_generated",
    preset_name: "logo_generated",
  };
}

export function applyBrandingTheme(branding: BrandingLike) {
  if (typeof document === "undefined") return;
  const theme = normalizeBranding(branding);
  const root = document.documentElement;
  root.style.setProperty("--erp-primary", theme.primary_color);
  root.style.setProperty("--erp-primary-dark", mix(theme.primary_color, "black", 0.25));
  root.style.setProperty("--erp-primary-soft", mix(theme.primary_color, "white", 0.86));
  root.style.setProperty("--erp-primary-text", readableTextColor(theme.primary_color));
  root.style.setProperty("--erp-secondary", theme.secondary_color);
  root.style.setProperty("--erp-accent", theme.accent_color);
  root.style.setProperty("--erp-sidebar", theme.sidebar_color);
  root.style.setProperty("--erp-sidebar-active", mix(theme.primary_color, "black", 0.35));
  root.style.setProperty("--erp-background", theme.background_color);
  root.style.setProperty("--erp-text", theme.text_color);
  root.style.setProperty("--erp-border-radius", `${theme.border_radius}px`);
  root.style.setProperty("--background", theme.background_color);
  root.style.setProperty("--foreground", theme.text_color);
}

export function getCachedBranding(): Partial<SchoolBranding> | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(BRANDING_CACHE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Partial<SchoolBranding>;
  } catch {
    window.localStorage.removeItem(BRANDING_CACHE_KEY);
    return null;
  }
}

export function cacheBrandingTheme(branding: BrandingLike) {
  if (typeof window === "undefined") return;
  const theme = normalizeBranding(branding);
  window.localStorage.setItem(BRANDING_CACHE_KEY, JSON.stringify(theme));
  window.dispatchEvent(new CustomEvent(BRANDING_UPDATED_EVENT, { detail: theme }));
}

export function clearCachedBranding() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(BRANDING_CACHE_KEY);
}

export async function extractDominantColorFromImage(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read logo file"));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("Could not load logo image"));
      img.onload = () => {
        const canvas = document.createElement("canvas");
        const size = 80;
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        if (!ctx) {
          reject(new Error("Browser canvas is not available"));
          return;
        }
        ctx.drawImage(img, 0, 0, size, size);
        const data = ctx.getImageData(0, 0, size, size).data;
        const buckets = new Map<string, { count: number; r: number; g: number; b: number }>();

        for (let i = 0; i < data.length; i += 16) {
          const r = data[i];
          const g = data[i + 1];
          const b = data[i + 2];
          const a = data[i + 3];
          if (a < 180) continue;
          const brightness = (r + g + b) / 3;
          if (brightness > 238 || brightness < 22) continue;
          const saturation = Math.max(r, g, b) - Math.min(r, g, b);
          if (saturation < 18 && brightness > 185) continue;
          const key = `${Math.round(r / 24)}-${Math.round(g / 24)}-${Math.round(b / 24)}`;
          const item = buckets.get(key) || { count: 0, r: 0, g: 0, b: 0 };
          item.count += 1;
          item.r += r;
          item.g += g;
          item.b += b;
          buckets.set(key, item);
        }

        const winner = Array.from(buckets.values()).sort((a, b) => b.count - a.count)[0];
        if (!winner || winner.count < 2) {
          resolve(DEFAULT_BRANDING.primary_color);
          return;
        }
        resolve(rgbToHex(winner.r / winner.count, winner.g / winner.count, winner.b / winner.count));
      };
      img.src = String(reader.result);
    };
    reader.readAsDataURL(file);
  });
}
