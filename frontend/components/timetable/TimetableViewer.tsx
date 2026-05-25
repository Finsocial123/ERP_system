"use client";

import { useEffect, useState } from "react";
import { RefreshCcw } from "lucide-react";

import { Button, Card } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { TimetableGrid } from "@/types";
import TimetableGridView from "@/components/timetable/TimetableGridView";

type Props = {
  role: "teacher" | "student" | "parent";
};

export default function TimetableViewer({ role }: Props) {
  const [grid, setGrid] = useState<TimetableGrid | null>(null);
  const [childrenGrids, setChildrenGrids] = useState<TimetableGrid[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      if (role === "parent") {
        const data = await apiFetch<TimetableGrid[]>("/timetable/my-children");
        setChildrenGrids(data);
        setGrid(null);
      } else {
        const endpoint = role === "teacher" ? "/timetable/my-teacher" : "/timetable/my-student";
        const data = await apiFetch<TimetableGrid>(endpoint);
        setGrid(data);
        setChildrenGrids([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load timetable");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Timetable</h1>
          <p className="text-sm text-slate-500">View weekly subject-period allocation with teacher and room details.</p>
        </div>
        <Button onClick={load} disabled={loading} className="flex items-center gap-2">
          <RefreshCcw size={16} /> Refresh
        </Button>
      </div>

      {error && <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {loading && <Card>Loading timetable...</Card>}

      {!loading && role !== "parent" && grid && (
        <section className="space-y-3">
          <h2 className="text-lg font-bold text-slate-900">{grid.title}</h2>
          <TimetableGridView grid={grid} />
        </section>
      )}

      {!loading && role === "parent" && (
        <div className="space-y-6">
          {childrenGrids.length === 0 && <Card>No child timetable found. Make sure parent contact is linked with student guardian details.</Card>}
          {childrenGrids.map((item, index) => (
            <section key={`${item.title}-${index}`} className="space-y-3">
              <h2 className="text-lg font-bold text-slate-900">{item.title}</h2>
              <TimetableGridView grid={item} />
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
