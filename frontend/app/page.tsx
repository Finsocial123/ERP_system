"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { dashboardPathForRole, getSavedAuth, getToken } from "@/lib/api";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const saved = getSavedAuth();
    if (getToken() && saved) {
      router.replace(dashboardPathForRole(saved.user.role, Boolean(saved.user.must_change_password)));
    } else {
      router.replace("/login");
    }
  }, [router]);

  return <main className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-600">Loading...</main>;
}
