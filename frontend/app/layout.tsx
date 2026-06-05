import type { Metadata } from "next";
import Script from "next/script";
import RouteShell from "@/components/RouteShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "School ERP",
  description: "School and college management portal",
};

const cachedThemeScript = `
(function () {
  try {
    var raw = localStorage.getItem("erp_school_branding_cache");
    if (!raw) return;
    var theme = JSON.parse(raw);
    var defaults = {
      primary_color: "#2563eb",
      secondary_color: "#0f172a",
      accent_color: "#22c55e",
      sidebar_color: "#0f172a",
      background_color: "#f8fafc",
      text_color: "#0f172a",
      border_radius: 16
    };
    theme = Object.assign(defaults, theme || {});
    function validHex(value, fallback) {
      return /^#[0-9a-f]{6}$/i.test(value || "") ? value : fallback;
    }
    function hexToRgb(hex) {
      hex = validHex(hex, defaults.primary_color).slice(1);
      return {
        r: parseInt(hex.slice(0, 2), 16),
        g: parseInt(hex.slice(2, 4), 16),
        b: parseInt(hex.slice(4, 6), 16)
      };
    }
    function rgbToHex(r, g, b) {
      function clamp(v) { return Math.max(0, Math.min(255, Math.round(v))); }
      return "#" + [clamp(r), clamp(g), clamp(b)].map(function (v) {
        return v.toString(16).padStart(2, "0");
      }).join("");
    }
    function mix(hex, target, amount) {
      var rgb = hexToRgb(hex);
      var t = target === "white" ? 255 : 0;
      return rgbToHex(rgb.r + (t - rgb.r) * amount, rgb.g + (t - rgb.g) * amount, rgb.b + (t - rgb.b) * amount);
    }
    function readableTextColor(background) {
      var rgb = hexToRgb(background);
      var luminance = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
      return luminance > 0.56 ? "#0f172a" : "#ffffff";
    }
    var root = document.documentElement;
    root.style.setProperty("--erp-primary", validHex(theme.primary_color, defaults.primary_color));
    root.style.setProperty("--erp-primary-dark", mix(theme.primary_color, "black", 0.25));
    root.style.setProperty("--erp-primary-soft", mix(theme.primary_color, "white", 0.86));
    root.style.setProperty("--erp-primary-text", readableTextColor(theme.primary_color));
    root.style.setProperty("--erp-secondary", validHex(theme.secondary_color, defaults.secondary_color));
    root.style.setProperty("--erp-accent", validHex(theme.accent_color, defaults.accent_color));
    root.style.setProperty("--erp-sidebar", validHex(theme.sidebar_color, defaults.sidebar_color));
    root.style.setProperty("--erp-sidebar-active", mix(theme.primary_color, "black", 0.35));
    root.style.setProperty("--erp-background", validHex(theme.background_color, defaults.background_color));
    root.style.setProperty("--erp-text", validHex(theme.text_color, defaults.text_color));
    root.style.setProperty("--erp-border-radius", (Number(theme.border_radius) || defaults.border_radius) + "px");
    root.style.setProperty("--background", validHex(theme.background_color, defaults.background_color));
    root.style.setProperty("--foreground", validHex(theme.text_color, defaults.text_color));
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <Script id="erp-cached-theme" strategy="beforeInteractive" dangerouslySetInnerHTML={{ __html: cachedThemeScript }} />
        <Script
          src="https://checkout.razorpay.com/v1/checkout.js"
          strategy="beforeInteractive"
        />
      </head>
      <body suppressHydrationWarning>
        <RouteShell>{children}</RouteShell>
      </body>
    </html>
  );
}
