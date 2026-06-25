"use client";

import { useEffect, useMemo, useState } from "react";
import { Edit2, Search, Trash2, UserPlus, X } from "lucide-react";

import AppShell from "@/components/AppShell";
import { Button, Card, Input, Label, Textarea } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { AcademicClass, Section, Student } from "@/types";

type StudentForm = {
  admission_no: string;
  roll_number: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  gender: string;
  date_of_birth: string;
  blood_group: string;
  photo_url: string;
  address: string;
  admission_date: string;
  class_id: string;
  section_id: string;
  guardian_full_name: string;
  guardian_relation: string;
  guardian_email: string;
  guardian_phone: string;
  guardian_occupation: string;
  guardian_address: string;
  create_login: boolean;
  password: string;
  create_parent_login: boolean;
  parent_password: string;
};

type StudentStatusFilter = "ACTIVE" | "DELETED" | "SUSPENDED" | "ALL";
type StudentToast = { type: "success" | "error"; message: string };

const emptyForm: StudentForm = {
  admission_no: "",
  roll_number: "",
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  gender: "",
  date_of_birth: "",
  blood_group: "",
  photo_url: "",
  address: "",
  admission_date: "",
  class_id: "",
  section_id: "",
  guardian_full_name: "",
  guardian_relation: "",
  guardian_email: "",
  guardian_phone: "",
  guardian_occupation: "",
  guardian_address: "",
  create_login: false,
  password: "",
  create_parent_login: false,
  parent_password: "",
};

function toNullable(value: string) {
  return value.trim() === "" ? null : value.trim();
}

function toNullableNumber(value: string) {
  return value === "" ? null : Number(value);
}

function studentStatusClass(student: Student) {
  if (!student.is_active || student.status === "DELETED") {
    return "bg-red-50 text-red-700";
  }
  if (student.status === "SUSPENDED") {
    return "bg-amber-50 text-amber-700";
  }
  return "bg-green-50 text-green-700";
}

export default function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([]);
  const [classes, setClasses] = useState<AcademicClass[]>([]);
  const [sections, setSections] = useState<Section[]>([]);
  const [form, setForm] = useState<StudentForm>(emptyForm);
  const [editing, setEditing] = useState<Student | null>(null);
  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<StudentStatusFilter>("ACTIVE");
  const [pendingDeactivate, setPendingDeactivate] = useState<Student | null>(null);
  const [toast, setToast] = useState<StudentToast | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [temporaryCredential, setTemporaryCredential] = useState("");

  const classNameById = useMemo(() => new Map(classes.map((item) => [item.id, item.name])), [classes]);
  const sectionNameById = useMemo(() => new Map(sections.map((item) => [item.id, item.name])), [sections]);
  const formSections = useMemo(() => sections.filter((item) => !form.class_id || item.class_id === Number(form.class_id)), [sections, form.class_id]);
  const sectionIdForName = (classId?: number | null, sectionName?: string | null) => {
    if (!classId || !sectionName) return null;
    const match = sections.find((item) => item.class_id === classId && item.name.trim().toLowerCase() === sectionName.trim().toLowerCase());
    return match?.id ?? null;
  };
  const studentSectionLabel = (student: Student) => student.section_name || (student.section_id ? sectionNameById.get(student.section_id) : "") || "";

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const setField = (name: keyof StudentForm, value: string | boolean) => {
    setForm((prev) => ({ ...prev, [name]: value, ...(name === "class_id" ? { section_id: "" } : {}) }));
  };

  const loadSetup = async () => {
    const [classData, sectionData] = await Promise.all([apiFetch<AcademicClass[]>("/classes"), apiFetch<Section[]>("/sections")]);
    setClasses(classData);
    setSections(sectionData);
  };

  const loadStudents = async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (classFilter) params.set("class_id", classFilter);
      if (statusFilter !== "ALL") params.set("status", statusFilter);
      if (statusFilter !== "ACTIVE") params.set("include_inactive", "true");
      const data = await apiFetch<Student[]>(`/students${params.toString() ? `?${params}` : ""}`);
      setStudents(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load students");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSetup().catch((err) => setError(err instanceof Error ? err.message : "Failed to load setup data"));
  }, []);

  useEffect(() => {
    loadStudents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classFilter, statusFilter]);

  const reset = () => {
    setForm(emptyForm);
    setEditing(null);
  };

  const buildPayload = () => {
    const guardian = form.guardian_full_name.trim()
      ? {
          full_name: form.guardian_full_name.trim(),
          relation: toNullable(form.guardian_relation),
          email: toNullable(form.guardian_email),
          phone: toNullable(form.guardian_phone),
          occupation: toNullable(form.guardian_occupation),
          address: toNullable(form.guardian_address),
        }
      : null;

    return {
      admission_no: form.admission_no.trim(),
      roll_number: toNullable(form.roll_number),
      first_name: form.first_name.trim(),
      last_name: toNullable(form.last_name),
      email: toNullable(form.email),
      phone: toNullable(form.phone),
      gender: toNullable(form.gender),
      date_of_birth: toNullable(form.date_of_birth),
      blood_group: toNullable(form.blood_group),
      photo_url: toNullable(form.photo_url),
      address: toNullable(form.address),
      admission_date: toNullable(form.admission_date),
      class_id: toNullableNumber(form.class_id),
      section_id: toNullableNumber(form.section_id),
      guardian,
      create_login: form.create_login,
      password: form.create_login && form.password ? form.password : null,
      create_parent_login: form.create_parent_login,
      parent_password: form.create_parent_login && form.parent_password ? form.parent_password : null,
    };
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setTemporaryCredential("");
    try {
      const payload = buildPayload();
      if (editing) {
        const updated = await apiFetch<Student>(`/students/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
        const messages: string[] = [];
        if (updated.parent_temporary_password) {
          messages.push(`Parent login created. Login ID: ${updated.parent_login_id || updated.guardian?.email || updated.guardian?.phone || `${updated.admission_no}-PARENT`}, temporary password: ${updated.parent_temporary_password}`);
        }
        setTemporaryCredential(messages.join(" | "));
      } else {
        const created = await apiFetch<Student>("/students", { method: "POST", body: JSON.stringify(payload) });
        const messages: string[] = [];
        if (created.temporary_password) {
          messages.push(`Student login created. Login ID: ${created.admission_no}, temporary password: ${created.temporary_password}`);
        }
        if (created.parent_temporary_password) {
          messages.push(`Parent login created. Login ID: ${created.parent_login_id || created.guardian?.email || created.guardian?.phone || `${created.admission_no}-PARENT`}, temporary password: ${created.parent_temporary_password}`);
        }
        setTemporaryCredential(messages.join(" | "));
      }
      reset();
      setToast({ type: "success", message: editing ? "Student updated successfully." : "Student added successfully." });
      await loadStudents();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Student save failed");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (student: Student) => {
    setEditing(student);
    setTemporaryCredential("");
    setForm({
      admission_no: student.admission_no ?? "",
      roll_number: student.roll_number ?? "",
      first_name: student.first_name ?? "",
      last_name: student.last_name ?? "",
      email: student.email ?? "",
      phone: student.phone ?? "",
      gender: student.gender ?? "",
      date_of_birth: student.date_of_birth ?? "",
      blood_group: student.blood_group ?? "",
      photo_url: student.photo_url ?? "",
      address: student.address ?? "",
      admission_date: student.admission_date ?? "",
      class_id: student.class_id ? String(student.class_id) : "",
      section_id: student.section_name ? String(sectionIdForName(student.class_id, student.section_name) ?? "") : student.section_id ? String(student.section_id) : "",
      guardian_full_name: student.guardian?.full_name ?? "",
      guardian_relation: student.guardian?.relation ?? "",
      guardian_email: student.guardian?.email ?? "",
      guardian_phone: student.guardian?.phone ?? "",
      guardian_occupation: student.guardian?.occupation ?? "",
      guardian_address: student.guardian?.address ?? "",
      create_login: false,
      password: "",
      create_parent_login: false,
      parent_password: "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const requestDeactivate = (student: Student) => {
    setError("");
    setPendingDeactivate(student);
  };

  const confirmDeactivate = async () => {
    if (!pendingDeactivate) return;
    setSaving(true);
    setError("");
    try {
      await apiFetch(`/students/${pendingDeactivate.id}`, { method: "DELETE" });
      setToast({ type: "success", message: `${pendingDeactivate.first_name} has been deactivated.` });
      setPendingDeactivate(null);
      await loadStudents();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to deactivate student";
      setError(message);
      setToast({ type: "error", message });
    } finally {
      setSaving(false);
    }
  };

  const activate = async (student: Student) => {
    setSaving(true);
    setError("");
    try {
      await apiFetch<Student>(`/students/${student.id}/activate`, { method: "PATCH" });
      setToast({ type: "success", message: `${student.first_name} has been activated.` });
      await loadStudents();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to activate student";
      setError(message);
      setToast({ type: "error", message });
    } finally {
      setSaving(false);
    }
  };

  const createParentLogin = async (student: Student) => {
    if (!student.guardian) {
      setError("Add guardian details before creating a parent login.");
      return;
    }
    setError("");
    setTemporaryCredential("");
    try {
      const updated = await apiFetch<Student>(`/students/${student.id}/parent-login`, { method: "POST", body: JSON.stringify({}) });
      if (updated.parent_temporary_password) {
        setTemporaryCredential(`Parent login created. Login ID: ${updated.parent_login_id || updated.guardian?.email || updated.guardian?.phone || `${updated.admission_no}-PARENT`}, temporary password: ${updated.parent_temporary_password}`);
      } else {
        setTemporaryCredential("Parent login is already linked for this guardian.");
      }
      await loadStudents();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create parent login");
    }
  };

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Students</h1>
        <p className="mt-1 text-sm text-slate-500">Add student profiles, guardian details and optional student login accounts.</p>
      </div>

      {toast && (
        <div className={`fixed right-5 top-5 z-50 rounded-2xl border px-4 py-3 text-sm font-semibold shadow-lg ${toast.type === "success" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-red-200 bg-red-50 text-red-700"}`}>
          {toast.message}
        </div>
      )}

      <Card>
        <form onSubmit={save} className="grid gap-4 md:grid-cols-3">
          <div><Label>Admission No *</Label><Input value={form.admission_no} onChange={(e) => setField("admission_no", e.target.value)} required /></div>
          <div><Label>Roll No</Label><Input value={form.roll_number} onChange={(e) => setField("roll_number", e.target.value)} /></div>
          <div><Label>Class</Label><select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={form.class_id} onChange={(e) => setField("class_id", e.target.value)}><option value="">Select class</option>{classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
          <div><Label>First Name *</Label><Input value={form.first_name} onChange={(e) => setField("first_name", e.target.value)} required /></div>
          <div><Label>Last Name</Label><Input value={form.last_name} onChange={(e) => setField("last_name", e.target.value)} /></div>
          <div><Label>Section</Label><select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={form.section_id} onChange={(e) => setField("section_id", e.target.value)}><option value="">Select section</option>{formSections.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
          <div><Label>Email</Label><Input type="email" value={form.email} onChange={(e) => setField("email", e.target.value)} /></div>
          <div><Label>Phone</Label><Input value={form.phone} onChange={(e) => setField("phone", e.target.value)} /></div>
          <div><Label>Gender</Label><select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={form.gender} onChange={(e) => setField("gender", e.target.value)}><option value="">Select gender</option><option>Male</option><option>Female</option><option>Other</option></select></div>
          <div><Label>Date of Birth</Label><Input type="date" value={form.date_of_birth} onChange={(e) => setField("date_of_birth", e.target.value)} /></div>
          <div><Label>Admission Date</Label><Input type="date" value={form.admission_date} onChange={(e) => setField("admission_date", e.target.value)} /></div>
          <div><Label>Blood Group</Label><Input value={form.blood_group} onChange={(e) => setField("blood_group", e.target.value)} placeholder="B+" /></div>
          <div className="md:col-span-3"><Label>Photo URL</Label><Input value={form.photo_url} onChange={(e) => setField("photo_url", e.target.value)} placeholder="Use Cloudinary/S3 URL for now" /></div>
          <div className="md:col-span-3"><Label>Address</Label><Textarea value={form.address} onChange={(e) => setField("address", e.target.value)} /></div>

          <div className="border-t border-slate-200 pt-4 md:col-span-3"><h2 className="font-semibold text-slate-900">Parent / Guardian Details</h2></div>
          <div><Label>Guardian Name</Label><Input value={form.guardian_full_name} onChange={(e) => setField("guardian_full_name", e.target.value)} /></div>
          <div><Label>Relation</Label><Input value={form.guardian_relation} onChange={(e) => setField("guardian_relation", e.target.value)} placeholder="Father / Mother / Guardian" /></div>
          <div><Label>Guardian Phone</Label><Input value={form.guardian_phone} onChange={(e) => setField("guardian_phone", e.target.value)} /></div>
          <div><Label>Guardian Email</Label><Input type="email" value={form.guardian_email} onChange={(e) => setField("guardian_email", e.target.value)} /></div>
          <div><Label>Occupation</Label><Input value={form.guardian_occupation} onChange={(e) => setField("guardian_occupation", e.target.value)} /></div>
          <div><Label>Guardian Address</Label><Input value={form.guardian_address} onChange={(e) => setField("guardian_address", e.target.value)} /></div>

          {!editing && (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 md:col-span-3">
              <label className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <input type="checkbox" checked={form.create_login} onChange={(e) => setField("create_login", e.target.checked)} />
                Create student login account
              </label>
              <p className="mt-1 text-xs text-slate-500">Student login ID will be the admission number. Leave password blank to auto-generate a temporary password.</p>
              {form.create_login && <div className="mt-3 max-w-sm"><Label>Temporary Password</Label><Input type="password" value={form.password} onChange={(e) => setField("password", e.target.value)} minLength={6} placeholder="Auto-generate if blank" /></div>}
            </div>
          )}

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 md:col-span-3">
            <label className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              <input type="checkbox" checked={form.create_parent_login} onChange={(e) => setField("create_parent_login", e.target.checked)} />
              Create parent login account
            </label>
            <p className="mt-1 text-xs text-slate-500">Parent login uses guardian email, phone, or admission number + -PARENT. Parent can view child dashboard, homework, timetable, results, fees, attendance and notices.</p>
            {form.create_parent_login && <div className="mt-3 max-w-sm"><Label>Parent Temporary Password</Label><Input type="password" value={form.parent_password} onChange={(e) => setField("parent_password", e.target.value)} minLength={6} placeholder="Auto-generate if blank" /></div>}
          </div>

          <div className="flex items-center gap-2 md:col-span-3">
            <Button disabled={saving} type="submit"><span className="inline-flex items-center gap-2"><UserPlus size={16} /> {editing ? "Update Student" : "Add Student"}</span></Button>
            {editing && <button type="button" onClick={reset} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"><X size={16} /> Cancel</button>}
          </div>
        </form>
        {temporaryCredential && <p className="mt-4 rounded-xl bg-green-50 px-3 py-2 text-sm text-green-800">{temporaryCredential}</p>}
        {error && <p className="mt-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      </Card>

      <Card className="mt-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="grid gap-3 md:grid-cols-3">
            <div><Label>Search student</Label><Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name, admission no, roll no" /></div>
            <div><Label>Filter by class</Label><select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={classFilter} onChange={(e) => setClassFilter(e.target.value)}><option value="">All classes</option>{classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
            <div><Label>Status</Label><select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as StudentStatusFilter)}><option value="ACTIVE">Active</option><option value="DELETED">Deactivated</option><option value="SUSPENDED">Suspended</option><option value="ALL">All students</option></select></div>
          </div>
          <Button type="button" onClick={loadStudents}><span className="inline-flex items-center gap-2"><Search size={16} /> Search</span></Button>
        </div>

        <div className="mt-5 overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-100 text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Student</th><th className="px-4 py-3">Admission</th><th className="px-4 py-3">Class</th><th className="px-4 py-3">Guardian</th><th className="px-4 py-3">Login</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Actions</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? <tr><td className="px-4 py-5 text-slate-500" colSpan={7}>Loading...</td></tr> : students.length === 0 ? <tr><td className="px-4 py-5 text-slate-500" colSpan={7}>No students found.</td></tr> : students.map((student) => (
                <tr key={student.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{student.first_name} {student.last_name}<p className="text-xs font-normal text-slate-500">{student.email || student.phone || "-"}</p></td>
                  <td className="px-4 py-3 text-slate-600">{student.admission_no}{student.roll_number ? ` / Roll ${student.roll_number}` : ""}</td>
                  <td className="px-4 py-3 text-slate-600">{student.class_id ? classNameById.get(student.class_id) : "-"} {studentSectionLabel(student) ? `- ${studentSectionLabel(student)}` : ""}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {student.guardian?.full_name || "-"}
                    {student.guardian?.user_id && <p className="text-xs text-green-700">Parent login created</p>}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    <p>Student: {student.user_id ? "Created" : "No login"}</p>
                    <p className="text-xs">Parent: {student.guardian?.user_id ? "Created" : "No login"}</p>
                  </td>
                  <td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${studentStatusClass(student)}`}>{student.status}</span></td>
                  <td className="flex flex-wrap gap-2 px-4 py-3">
                    <button onClick={() => startEdit(student)} className="rounded-lg border border-slate-200 p-2 hover:bg-slate-100" title="Edit student"><Edit2 size={15} /></button>
                    {student.guardian && !student.guardian.user_id && <button onClick={() => createParentLogin(student)} className="rounded-lg border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100">Parent Login</button>}
                    {student.is_active ? (
                      <button onClick={() => requestDeactivate(student)} className="rounded-lg border border-red-200 p-2 text-red-600 hover:bg-red-50" title="Deactivate student"><Trash2 size={15} /></button>
                    ) : (
                      <button onClick={() => activate(student)} className="rounded-lg border border-emerald-200 px-2 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-50" title="Activate student">Activate</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {pendingDeactivate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 px-4">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl">
            <h2 className="text-lg font-bold text-slate-900">Deactivate student?</h2>
            <p className="mt-2 text-sm text-slate-600">
              {pendingDeactivate.first_name} {pendingDeactivate.last_name || ""} will be hidden from active student lists. Admin can activate this student again from the Deactivated status filter.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setPendingDeactivate(null)} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50" disabled={saving}>Cancel</button>
              <button type="button" onClick={confirmDeactivate} className="rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60" disabled={saving}>{saving ? "Deactivating..." : "Deactivate"}</button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
