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
};

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
};

function toNullable(value: string) {
  return value.trim() === "" ? null : value.trim();
}

function toNullableNumber(value: string) {
  return value === "" ? null : Number(value);
}

export default function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([]);
  const [classes, setClasses] = useState<AcademicClass[]>([]);
  const [sections, setSections] = useState<Section[]>([]);
  const [form, setForm] = useState<StudentForm>(emptyForm);
  const [editing, setEditing] = useState<Student | null>(null);
  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [temporaryCredential, setTemporaryCredential] = useState("");

  const classNameById = useMemo(() => new Map(classes.map((item) => [item.id, item.name])), [classes]);
  const sectionNameById = useMemo(() => new Map(sections.map((item) => [item.id, item.name])), [sections]);
  const formSections = useMemo(() => sections.filter((item) => !form.class_id || item.class_id === Number(form.class_id)), [sections, form.class_id]);

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
  }, [classFilter]);

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
        await apiFetch(`/students/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
      } else {
        const created = await apiFetch<Student>("/students", { method: "POST", body: JSON.stringify(payload) });
        if (created.temporary_password) {
          setTemporaryCredential(`Student login created. Login ID: ${created.admission_no}, temporary password: ${created.temporary_password}`);
        }
      }
      reset();
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
      section_id: student.section_id ? String(student.section_id) : "",
      guardian_full_name: student.guardian?.full_name ?? "",
      guardian_relation: student.guardian?.relation ?? "",
      guardian_email: student.guardian?.email ?? "",
      guardian_phone: student.guardian?.phone ?? "",
      guardian_occupation: student.guardian?.occupation ?? "",
      guardian_address: student.guardian?.address ?? "",
      create_login: false,
      password: "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const deactivate = async (student: Student) => {
    if (!confirm(`Deactivate ${student.first_name}?`)) return;
    setError("");
    try {
      await apiFetch(`/students/${student.id}`, { method: "DELETE" });
      await loadStudents();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to deactivate student");
    }
  };

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Students</h1>
        <p className="mt-1 text-sm text-slate-500">Add student profiles, guardian details and optional student login accounts.</p>
      </div>

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
          <div className="grid gap-3 md:grid-cols-2">
            <div><Label>Search student</Label><Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name, admission no, roll no" /></div>
            <div><Label>Filter by class</Label><select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={classFilter} onChange={(e) => setClassFilter(e.target.value)}><option value="">All classes</option>{classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
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
                  <td className="px-4 py-3 text-slate-600">{student.class_id ? classNameById.get(student.class_id) : "-"} {student.section_id ? `- ${sectionNameById.get(student.section_id)}` : ""}</td>
                  <td className="px-4 py-3 text-slate-600">{student.guardian?.full_name || "-"}</td>
                  <td className="px-4 py-3 text-slate-600">{student.user_id ? "Created" : "No login"}</td>
                  <td className="px-4 py-3"><span className="rounded-full bg-green-50 px-2 py-1 text-xs font-semibold text-green-700">{student.status}</span></td>
                  <td className="flex gap-2 px-4 py-3"><button onClick={() => startEdit(student)} className="rounded-lg border border-slate-200 p-2 hover:bg-slate-100"><Edit2 size={15} /></button><button onClick={() => deactivate(student)} className="rounded-lg border border-red-200 p-2 text-red-600 hover:bg-red-50"><Trash2 size={15} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </AppShell>
  );
}
