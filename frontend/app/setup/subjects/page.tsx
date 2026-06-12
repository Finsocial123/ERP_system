"use client";

import { useEffect, useMemo, useState } from "react";
import { Edit2, Plus, Trash2, X } from "lucide-react";

import AppShell from "@/components/AppShell";
import { AppSection } from "@/components/CrudManager";
import { Button, Card, Input, Label } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { AcademicClass, Department, Subject } from "@/types";

type SubjectForm = {
  name: string;
  code: string;
  department_id: string;
  class_id: string;
};

const emptyForm: SubjectForm = {
  name: "",
  code: "",
  department_id: "",
  class_id: "",
};

function toNullableNumber(value: string) {
  return value === "" ? null : Number(value);
}

export default function SubjectsPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [classes, setClasses] = useState<AcademicClass[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [form, setForm] = useState<SubjectForm>(emptyForm);
  const [editing, setEditing] = useState<Subject | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const classById = useMemo(() => new Map(classes.map((item) => [item.id, item.name])), [classes]);
  const departmentById = useMemo(() => new Map(departments.map((item) => [item.id, item.name])), [departments]);

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      const [subjectData, classData, departmentData] = await Promise.all([
        apiFetch<Subject[]>("/subjects"),
        apiFetch<AcademicClass[]>("/classes"),
        apiFetch<Department[]>("/departments"),
      ]);
      setSubjects(subjectData);
      setClasses(classData);
      setDepartments(departmentData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load subjects");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const reset = () => {
    setForm(emptyForm);
    setEditing(null);
  };

  const startEdit = (subject: Subject) => {
    setEditing(subject);
    setForm({
      name: subject.name,
      code: subject.code || "",
      department_id: subject.department_id ? String(subject.department_id) : "",
      class_id: subject.class_id ? String(subject.class_id) : "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = {
        name: form.name.trim(),
        code: form.code.trim() || null,
        department_id: toNullableNumber(form.department_id),
        class_id: Number(form.class_id),
      };
      await apiFetch(editing ? `/subjects/${editing.id}` : "/subjects", {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      reset();
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save subject");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (subject: Subject) => {
    if (!confirm(`Delete ${subject.name}?`)) return;
    setError("");
    try {
      await apiFetch(`/subjects/${subject.id}`, { method: "DELETE" });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete subject");
    }
  };

  return (
    <AppShell>
      <AppSection title="Subjects" description="Create subjects for a specific class. The class is now required so other modules can show only class-specific subjects.">
        <Card>
          <form onSubmit={save} className="grid gap-4 md:grid-cols-2">
            <div>
              <Label>Subject Name *</Label>
              <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required placeholder="Mathematics" />
            </div>
            <div>
              <Label>Code</Label>
              <Input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} placeholder="MATH" />
            </div>
            <div>
              <Label>Class *</Label>
              <select required className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={form.class_id} onChange={(event) => setForm({ ...form, class_id: event.target.value })}>
                <option value="">Select class</option>
                {classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
            <div>
              <Label>Department</Label>
              <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={form.department_id} onChange={(event) => setForm({ ...form, department_id: event.target.value })}>
                <option value="">No department</option>
                {departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
            <div className="flex items-end gap-2 md:col-span-2">
              <Button type="submit" disabled={saving}>
                <span className="inline-flex items-center gap-2"><Plus size={16} /> {editing ? "Update Subject" : "Create Subject"}</span>
              </Button>
              {editing && <button type="button" onClick={reset} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"><X size={16} /> Cancel</button>}
            </div>
          </form>
          {error && <p className="mt-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        </Card>

        <Card className="mt-6 overflow-hidden p-0">
          {loading ? (
            <p className="p-5 text-sm text-slate-500">Loading...</p>
          ) : subjects.length === 0 ? (
            <p className="p-5 text-sm text-slate-500">No subjects yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-100 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">ID</th>
                    <th className="px-4 py-3">Subject</th>
                    <th className="px-4 py-3">Code</th>
                    <th className="px-4 py-3">Class</th>
                    <th className="px-4 py-3">Department</th>
                    <th className="px-4 py-3">Active</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {subjects.map((subject) => (
                    <tr key={subject.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 text-slate-700">{subject.id}</td>
                      <td className="px-4 py-3 font-semibold text-slate-900">{subject.name}</td>
                      <td className="px-4 py-3 text-slate-700">{subject.code || "-"}</td>
                      <td className="px-4 py-3 text-slate-700">{subject.class_id ? classById.get(subject.class_id) || subject.class_id : "Missing class"}</td>
                      <td className="px-4 py-3 text-slate-700">{subject.department_id ? departmentById.get(subject.department_id) || subject.department_id : "-"}</td>
                      <td className="px-4 py-3 text-slate-700">{subject.is_active ? "Yes" : "No"}</td>
                      <td className="flex gap-2 px-4 py-3">
                        <button type="button" onClick={() => startEdit(subject)} className="rounded-lg border border-slate-200 p-2 hover:bg-slate-100"><Edit2 size={15} /></button>
                        <button type="button" onClick={() => remove(subject)} className="rounded-lg border border-red-200 p-2 text-red-600 hover:bg-red-50"><Trash2 size={15} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </AppSection>
    </AppShell>
  );
}
