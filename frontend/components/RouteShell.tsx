"use client";

import { usePathname } from "next/navigation";

import AppShell from "@/components/AppShell";

const PUBLIC_ROUTES = new Set([
  "/",
  "/login",
  "/register-school",
  "/forgot-password",
  "/reset-password",
]);

function isPublicRoute(pathname: string | null) {
  if (!pathname) return true;
  if (PUBLIC_ROUTES.has(pathname)) return true;
  return pathname.startsWith("/reset-password/");
}

export default function RouteShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (isPublicRoute(pathname)) {
    return <>{children}</>;
  }

  return <AppShell>{children}</AppShell>;
}
