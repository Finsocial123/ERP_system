"use client";

import { useEffect, useMemo, useState } from "react";
import { Edit2, Eye, Plus, RefreshCcw, Search, Trash2, X } from "lucide-react";

import { AppSection } from "@/components/CrudManager";
import { Button, Card, Input, Label, Textarea } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { TimetableDay, TimetableEntry, TimetableGrid, TimetableMeta, TimetablePeriod } from "@/types";
import TimetableGridView from "@/components/timetable/TimetableGridView";

type PeriodForm = {
  period_number: string;
  name: string;
  start_time: string;
  end_time: string;
  is_break: boolean;
  is_active: boolean;
};

type DayForm = {
  day_of_week: string;
  display_name: string;
  sort_order: string;
  is_active: boolean;
};

type EntryForm = {
  academic_session_id: string;
  class_id: string;
  section_id: string;
  day_id: string;
  period_id: string;
  subject_id: string;
  teacher_id: string;
  room: string;
  note: string;
  is_active: boolean;
};

const emptyPeriod: PeriodForm = { period_number: "", name: "", start_time: "", end_time: "", is_break: false, is_active: true };
const emptyDay: DayForm = { day_of_week: "MONDAY", display_name: "Monday", sort_order: "1", is_active: true };
const emptyEntry: EntryForm = {
  academic_session_id: "",
  class_id: "",
  section_id: "",
  day_id: "",
  period_id: "",
  subject_id: "",
  teacher_id: "",
  room: "",
  note: "",
  is_active: true,
};

const days = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"];

function SelectBox({ value, onChange, children, required = false }: { value: string; onChange: (value: string) => void; children: React.ReactNode; required?: boolean }) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      required={required}
      className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none transition focus:border-slate-400"
    >
      {children}
    </select>
  );
}

function boolPayload(value: boolean) {
  return Boolean(value);
}

function formatTime(value?: string | null) {
  if (!value) return "-";
  return value.slice(0, 5);
}

function displaySlot(entry: TimetableEntry) {
  return `${entry.day_name || "Day"} · ${entry.period_name || "Period"}`;
}

export default function TimetableManager() {
  const [tab, setTab] = useState<"entries" | "periods" | "days" | "views">("entries");
  const [meta, setMeta] = useState<TimetableMeta | null>(null);
  const [entries, setEntries] = useState<TimetableEntry[]>([]);
  const [periodForm, setPeriodForm] = useState<PeriodForm>(emptyPeriod);
  const [dayForm, setDayForm] = useState<DayForm>(emptyDay);
  const [entryForm, setEntryForm] = useState<EntryForm>(emptyEntry);
  const [editingPeriod, setEditingPeriod] = useState<TimetablePeriod | null>(null);
  const [editingDay, setEditingDay] = useState<TimetableDay | null>(null);
  const [editingEntry, setEditingEntry] = useState<TimetableEntry | null>(null);
  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [teacherFilter, setTeacherFilter] = useState("");
  const [viewMode, setViewMode] = useState<"class" | "teacher">("class");
  const [viewClassId, setViewClassId] = useState("");
  const [viewSectionId, setViewSectionId] = useState("");
  const [viewTeacherId, setViewTeacherId] = useState("");
  const [grid, setGrid] = useState<TimetableGrid | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const filteredSectionsForEntry = useMemo(() => {
    if (!meta) return [];
    if (!entryForm.class_id) return meta.sections;
    return meta.sections.filter((item) => item.extra === entryForm.class_id);
  }, [entryForm.class_id, meta]);

  const filteredSubjectsForEntry = useMemo(() => {
    if (!meta || !entryForm.class_id) return [];
    return meta.subjects.filter((item) => item.extra === entryForm.class_id);
  }, [entryForm.class_id, meta]);

  const filteredSectionsForView = useMemo(() => {
    if (!meta) return [];
    if (!viewClassId) return meta.sections;
    return meta.sections.filter((item) => item.extra === viewClassId);
  }, [meta, viewClassId]);

  const sectionIdForName = (classId?: number | null, sectionName?: string | null) => {
    if (!meta || !classId || !sectionName) return null;
    const match = meta.sections.find((item) => item.extra === String(classId) && item.name.trim().toLowerCase() === sectionName.trim().toLowerCase());
    return match?.id ?? null;
  };

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (classFilter) params.set("class_id", classFilter);
      if (teacherFilter) params.set("teacher_id", teacherFilter);
      const [metaData, entryData] = await Promise.all([
        apiFetch<TimetableMeta>("/timetable/meta"),
        apiFetch<TimetableEntry[]>(`/timetable/entries${params.toString() ? `?${params.toString()}` : ""}`),
      ]);
      setMeta(metaData);
      setEntries(entryData);
      setEntryForm((prev) => ({ ...prev, academic_session_id: prev.academic_session_id || String(metaData.current_academic_session_id || "") }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load timetable");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classFilter, teacherFilter]);

  const resetPeriod = () => {
    setPeriodForm(emptyPeriod);
    setEditingPeriod(null);
  };

  const resetDay = () => {
    setDayForm(emptyDay);
    setEditingDay(null);
  };

  const resetEntry = () => {
    setEntryForm({ ...emptyEntry, academic_session_id: String(meta?.current_academic_session_id || "") });
    setEditingEntry(null);
  };

  const savePeriod = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    const payload = {
      period_number: Number(periodForm.period_number),
      name: periodForm.name.trim(),
      start_time: periodForm.start_time || null,
      end_time: periodForm.end_time || null,
      is_break: boolPayload(periodForm.is_break),
      is_active: boolPayload(periodForm.is_active),
    };
    try {
      await apiFetch(editingPeriod ? `/timetable/periods/${editingPeriod.id}` : "/timetable/periods", {
        method: editingPeriod ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      setSuccess(editingPeriod ? "Period updated successfully" : "Period created successfully");
      resetPeriod();
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save period");
    } finally {
      setSaving(false);
    }
  };

  const saveDay = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    const payload = {
      day_of_week: dayForm.day_of_week,
      display_name: dayForm.display_name.trim(),
      sort_order: Number(dayForm.sort_order),
      is_active: boolPayload(dayForm.is_active),
    };
    try {
      await apiFetch(editingDay ? `/timetable/days/${editingDay.id}` : "/timetable/days", {
        method: editingDay ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      setSuccess(editingDay ? "Day updated successfully" : "Day created successfully");
      resetDay();
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save day");
    } finally {
      setSaving(false);
    }
  };

  const saveEntry = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    const payload = {
      academic_session_id: entryForm.academic_session_id ? Number(entryForm.academic_session_id) : null,
      class_id: Number(entryForm.class_id),
      section_id: entryForm.section_id ? Number(entryForm.section_id) : null,
      day_id: Number(entryForm.day_id),
      period_id: Number(entryForm.period_id),
      subject_id: entryForm.subject_id ? Number(entryForm.subject_id) : null,
      teacher_id: entryForm.teacher_id ? Number(entryForm.teacher_id) : null,
      room: entryForm.room.trim() || null,
      note: entryForm.note.trim() || null,
      is_active: boolPayload(entryForm.is_active),
    };
    try {
      await apiFetch(editingEntry ? `/timetable/entries/${editingEntry.id}` : "/timetable/entries", {
        method: editingEntry ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      setSuccess(editingEntry ? "Timetable entry updated successfully" : "Timetable entry created successfully");
      resetEntry();
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save timetable entry");
    } finally {
      setSaving(false);
    }
  };

  const startEditPeriod = (item: TimetablePeriod) => {
    setEditingPeriod(item);
    setPeriodForm({
      period_number: String(item.period_number),
      name: item.name,
      start_time: item.start_time?.slice(0, 5) || "",
      end_time: item.end_time?.slice(0, 5) || "",
      is_break: item.is_break,
      is_active: item.is_active,
    });
    setTab("periods");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const startEditDay = (item: TimetableDay) => {
    setEditingDay(item);
    setDayForm({ day_of_week: item.day_of_week, display_name: item.display_name, sort_order: String(item.sort_order), is_active: item.is_active });
    setTab("days");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const startEditEntry = (item: TimetableEntry) => {
    setEditingEntry(item);
    setEntryForm({
      academic_session_id: item.academic_session_id ? String(item.academic_session_id) : "",
      class_id: String(item.class_id),
      section_id: item.section_name ? String(sectionIdForName(item.class_id, item.section_name) ?? "") : item.section_id ? String(item.section_id) : "",
      day_id: String(item.day_id),
      period_id: String(item.period_id),
      subject_id: item.subject_id ? String(item.subject_id) : "",
      teacher_id: item.teacher_id ? String(item.teacher_id) : "",
      room: item.room || "",
      note: item.note || "",
      is_active: item.is_active,
    });
    setTab("entries");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const deleteItem = async (path: string, message: string) => {
    if (!confirm(message)) return;
    setError("");
    setSuccess("");
    try {
      await apiFetch(path, { method: "DELETE" });
      setSuccess("Deleted successfully");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  const loadGrid = async () => {
    setError("");
    setGrid(null);
    try {
      if (viewMode === "class") {
        if (!viewClassId) throw new Error("Select a class first");
        const params = new URLSearchParams({ class_id: viewClassId });
        if (viewSectionId) params.set("section_id", viewSectionId);
        const data = await apiFetch<TimetableGrid>(`/timetable/view/class?${params.toString()}`);
        setGrid(data);
      } else {
        if (!viewTeacherId) throw new Error("Select a teacher first");
        const data = await apiFetch<TimetableGrid>(`/timetable/view/teacher?teacher_id=${viewTeacherId}`);
        setGrid(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load timetable view");
    }
  };

  const visibleEntries = entries.filter((item) => {
    if (!search.trim()) return true;
    const query = search.toLowerCase();
    return [item.class_name, item.section_name, item.subject_name, item.teacher_name, item.day_name, item.period_name, item.room]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });

  return (
    <AppSection
      title="Timetable Management"
      description="Create periods, active school days, class timetable slots, teacher timetable views, subject-period allocation, and optional room allocation."
    >
      <div className="mb-5 flex flex-wrap gap-2">
        {[
          ["entries", "Class Timetable"],
          ["periods", "Period Setup"],
          ["days", "Day Setup"],
          ["views", "View Timetable"],
        ].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key as typeof tab)}
            className={`rounded-xl px-4 py-2 text-sm font-semibold ${tab === key ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}
          >
            {label}
          </button>
        ))}
        <Button onClick={loadData} disabled={loading} className="ml-auto flex items-center gap-2">
          <RefreshCcw size={16} /> Refresh
        </Button>
      </div>

      {error && <div className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {success && <div className="mb-4 rounded-xl bg-green-50 p-3 text-sm text-green-700">{success}</div>}

      {tab === "periods" && (
        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <Card>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">{editingPeriod ? "Edit Period" : "Add Period"}</h2>
              {editingPeriod && <button onClick={resetPeriod} className="rounded-lg border p-2 text-slate-500"><X size={16} /></button>}
            </div>
            <form onSubmit={savePeriod} className="grid gap-4 md:grid-cols-2">
              <div><Label>Period Number</Label><Input type="number" min={1} value={periodForm.period_number} onChange={(e) => setPeriodForm({ ...periodForm, period_number: e.target.value })} required /></div>
              <div><Label>Name</Label><Input value={periodForm.name} onChange={(e) => setPeriodForm({ ...periodForm, name: e.target.value })} placeholder="Period 1" required /></div>
              <div><Label>Start Time</Label><Input type="time" value={periodForm.start_time} onChange={(e) => setPeriodForm({ ...periodForm, start_time: e.target.value })} /></div>
              <div><Label>End Time</Label><Input type="time" value={periodForm.end_time} onChange={(e) => setPeriodForm({ ...periodForm, end_time: e.target.value })} /></div>
              <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={periodForm.is_break} onChange={(e) => setPeriodForm({ ...periodForm, is_break: e.target.checked })} /> Break period</label>
              <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={periodForm.is_active} onChange={(e) => setPeriodForm({ ...periodForm, is_active: e.target.checked })} /> Active</label>
              <Button disabled={saving} className="md:col-span-2 flex items-center justify-center gap-2"><Plus size={16} /> {editingPeriod ? "Update Period" : "Add Period"}</Button>
            </form>
          </Card>
          <Card>
            <h2 className="mb-4 text-lg font-bold text-slate-900">Periods</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead><tr className="text-left text-slate-500"><th className="py-2">No.</th><th>Name</th><th>Time</th><th>Type</th><th>Status</th><th></th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {meta?.periods.map((item) => (
                    <tr key={item.id}>
                      <td className="py-3">{item.period_number}</td><td>{item.name}</td><td>{formatTime(item.start_time)} - {formatTime(item.end_time)}</td><td>{item.is_break ? "Break" : "Class"}</td><td>{item.is_active ? "Active" : "Inactive"}</td>
                      <td className="flex gap-2 py-3"><button onClick={() => startEditPeriod(item)} className="rounded-lg border p-2"><Edit2 size={15} /></button><button onClick={() => deleteItem(`/timetable/periods/${item.id}`, "Delete this period?")} className="rounded-lg border p-2 text-red-600"><Trash2 size={15} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {tab === "days" && (
        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <Card>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">{editingDay ? "Edit Day" : "Add Day"}</h2>
              {editingDay && <button onClick={resetDay} className="rounded-lg border p-2 text-slate-500"><X size={16} /></button>}
            </div>
            <form onSubmit={saveDay} className="grid gap-4 md:grid-cols-2">
              <div><Label>Day</Label><SelectBox value={dayForm.day_of_week} onChange={(value) => setDayForm({ ...dayForm, day_of_week: value, display_name: value.charAt(0) + value.slice(1).toLowerCase() })} required>{days.map((day) => <option key={day} value={day}>{day}</option>)}</SelectBox></div>
              <div><Label>Display Name</Label><Input value={dayForm.display_name} onChange={(e) => setDayForm({ ...dayForm, display_name: e.target.value })} required /></div>
              <div><Label>Sort Order</Label><Input type="number" min={1} max={7} value={dayForm.sort_order} onChange={(e) => setDayForm({ ...dayForm, sort_order: e.target.value })} required /></div>
              <label className="mt-7 flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={dayForm.is_active} onChange={(e) => setDayForm({ ...dayForm, is_active: e.target.checked })} /> Active</label>
              <Button disabled={saving} className="md:col-span-2 flex items-center justify-center gap-2"><Plus size={16} /> {editingDay ? "Update Day" : "Add Day"}</Button>
            </form>
          </Card>
          <Card>
            <h2 className="mb-4 text-lg font-bold text-slate-900">Days</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead><tr className="text-left text-slate-500"><th className="py-2">Order</th><th>Day</th><th>Name</th><th>Status</th><th></th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {meta?.days.map((item) => (
                    <tr key={item.id}>
                      <td className="py-3">{item.sort_order}</td><td>{item.day_of_week}</td><td>{item.display_name}</td><td>{item.is_active ? "Active" : "Inactive"}</td>
                      <td className="flex gap-2 py-3"><button onClick={() => startEditDay(item)} className="rounded-lg border p-2"><Edit2 size={15} /></button><button onClick={() => deleteItem(`/timetable/days/${item.id}`, "Delete this day?")} className="rounded-lg border p-2 text-red-600"><Trash2 size={15} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {tab === "entries" && (
        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.35fr]">
          <Card>
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-slate-900">{editingEntry ? "Edit Slot" : "Add Timetable Slot"}</h2>
                <p className="text-sm text-slate-500">One class/section can have one slot per day and period. Teacher and room conflicts are blocked.</p>
              </div>
              {editingEntry && <button onClick={resetEntry} className="rounded-lg border p-2 text-slate-500"><X size={16} /></button>}
            </div>
            <form onSubmit={saveEntry} className="grid gap-4 md:grid-cols-2">
              <div><Label>Academic Session</Label><SelectBox value={entryForm.academic_session_id} onChange={(value) => setEntryForm({ ...entryForm, academic_session_id: value })}><option value="">Current/None</option>{meta?.academic_sessions.map((item) => <option key={item.id} value={item.id}>{item.name}{item.extra === "active" ? " (Active)" : ""}</option>)}</SelectBox></div>
              <div><Label>Class</Label><SelectBox value={entryForm.class_id} onChange={(value) => setEntryForm({ ...entryForm, class_id: value, section_id: "", subject_id: "" })} required><option value="">Select class</option>{meta?.classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectBox></div>
              <div><Label>Section</Label><SelectBox value={entryForm.section_id} onChange={(value) => setEntryForm({ ...entryForm, section_id: value })}><option value="">All sections</option>{filteredSectionsForEntry.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectBox></div>
              <div><Label>Day</Label><SelectBox value={entryForm.day_id} onChange={(value) => setEntryForm({ ...entryForm, day_id: value })} required><option value="">Select day</option>{meta?.days.filter((d) => d.is_active).map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</SelectBox></div>
              <div><Label>Period</Label><SelectBox value={entryForm.period_id} onChange={(value) => setEntryForm({ ...entryForm, period_id: value })} required><option value="">Select period</option>{meta?.periods.filter((p) => p.is_active).map((item) => <option key={item.id} value={item.id}>P{item.period_number} - {item.name}</option>)}</SelectBox></div>
              <div><Label>Subject</Label><SelectBox value={entryForm.subject_id} onChange={(value) => setEntryForm({ ...entryForm, subject_id: value })}><option value="">{entryForm.class_id ? "Optional subject" : "Select class first"}</option>{filteredSubjectsForEntry.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectBox></div>
              <div><Label>Teacher</Label><SelectBox value={entryForm.teacher_id} onChange={(value) => setEntryForm({ ...entryForm, teacher_id: value })}><option value="">Optional teacher</option>{meta?.teachers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectBox></div>
              <div><Label>Room Optional</Label><Input value={entryForm.room} onChange={(e) => setEntryForm({ ...entryForm, room: e.target.value })} placeholder="Room 101 / Lab A" /></div>
              <div className="md:col-span-2"><Label>Note</Label><Textarea value={entryForm.note} onChange={(e) => setEntryForm({ ...entryForm, note: e.target.value })} placeholder="Optional note" /></div>
              <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={entryForm.is_active} onChange={(e) => setEntryForm({ ...entryForm, is_active: e.target.checked })} /> Active</label>
              <Button disabled={saving} className="md:col-span-2 flex items-center justify-center gap-2"><Plus size={16} /> {editingEntry ? "Update Slot" : "Add Slot"}</Button>
            </form>
          </Card>
          <Card>
            <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
              <div className="relative flex-1"><Search className="absolute left-3 top-2.5 text-slate-400" size={17} /><Input className="pl-9" placeholder="Search by class, teacher, subject, room..." value={search} onChange={(e) => setSearch(e.target.value)} /></div>
              <SelectBox value={classFilter} onChange={setClassFilter}><option value="">All classes</option>{meta?.classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectBox>
              <SelectBox value={teacherFilter} onChange={setTeacherFilter}><option value="">All teachers</option>{meta?.teachers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectBox>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead><tr className="text-left text-slate-500"><th className="py-2">Slot</th><th>Class</th><th>Subject</th><th>Teacher</th><th>Room</th><th>Status</th><th></th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {visibleEntries.map((item) => (
                    <tr key={item.id}>
                      <td className="py-3">{displaySlot(item)}</td>
                      <td>{item.class_name}{item.section_name ? ` - ${item.section_name}` : ""}</td>
                      <td>{item.subject_name || "-"}</td>
                      <td>{item.teacher_name || "-"}</td>
                      <td>{item.room || "-"}</td>
                      <td>{item.is_active ? "Active" : "Inactive"}</td>
                      <td className="flex gap-2 py-3"><button onClick={() => startEditEntry(item)} className="rounded-lg border p-2"><Edit2 size={15} /></button><button onClick={() => deleteItem(`/timetable/entries/${item.id}`, "Delete this timetable slot?")} className="rounded-lg border p-2 text-red-600"><Trash2 size={15} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!visibleEntries.length && <p className="py-8 text-center text-sm text-slate-500">No timetable slots found.</p>}
            </div>
          </Card>
        </div>
      )}

      {tab === "views" && (
        <div className="space-y-6">
          <Card>
            <div className="grid gap-4 md:grid-cols-4">
              <div><Label>View Type</Label><SelectBox value={viewMode} onChange={(value) => { setViewMode(value as "class" | "teacher"); setGrid(null); }}><option value="class">View by class</option><option value="teacher">View by teacher</option></SelectBox></div>
              {viewMode === "class" ? (
                <>
                  <div><Label>Class</Label><SelectBox value={viewClassId} onChange={(value) => { setViewClassId(value); setViewSectionId(""); }}><option value="">Select class</option>{meta?.classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectBox></div>
                  <div><Label>Section</Label><SelectBox value={viewSectionId} onChange={setViewSectionId}><option value="">All sections</option>{filteredSectionsForView.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectBox></div>
                </>
              ) : (
                <div><Label>Teacher</Label><SelectBox value={viewTeacherId} onChange={setViewTeacherId}><option value="">Select teacher</option>{meta?.teachers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectBox></div>
              )}
              <div className="flex items-end"><Button onClick={loadGrid} className="flex w-full items-center justify-center gap-2"><Eye size={16} /> View</Button></div>
            </div>
          </Card>
          {grid && (
            <section className="space-y-3">
              <h2 className="text-lg font-bold text-slate-900">{grid.title}</h2>
              <TimetableGridView grid={grid} />
            </section>
          )}
        </div>
      )}
    </AppSection>
  );
}
