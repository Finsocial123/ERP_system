"use client";

import { useEffect, useMemo, useState } from "react";
import { Edit2, Link2, Search, Trash2, UserPlus, UserRound, X } from "lucide-react";

import AppShell from "@/components/AppShell";
import { Button, Card, Input, Label, Textarea } from "@/components/ui";
import { apiFetch, fileUrl } from "@/lib/api";
import type { AcademicClass, AcademicSession, ClassTeacherAssignment, Department, Section, Subject, Teacher, TeacherSubjectAssignment } from "@/types";

type TeacherForm = {
  employee_id: string;
  full_name: string;
  email: string;
  phone: string;
  gender: string;
  department_id: string;
  qualification: string;
  specialization: string;
  joining_date: string;
  photo_url: string;
  address: string;
  create_login: boolean;
  password: string;
};

type SubjectForm = {
  teacher_id: string;
  subject_id: string;
  class_id: string;
  section_id: string;
};

type ClassTeacherForm = {
  teacher_id: string;
  class_id: string;
  section_id: string;
  academic_session_id: string;
};

const emptyTeacherForm: TeacherForm = {
  employee_id: "",
  full_name: "",
  email: "",
  phone: "",
  gender: "",
  department_id: "",
  qualification: "",
  specialization: "",
  joining_date: "",
  photo_url: "",
  address: "",
  create_login: false,
  password: "",
};

const emptySubjectForm: SubjectForm = { teacher_id: "", subject_id: "", class_id: "", section_id: "" };
const emptyClassTeacherForm: ClassTeacherForm = { teacher_id: "", class_id: "", section_id: "", academic_session_id: "" };

function toNullable(value: string) {
  return value.trim() === "" ? null : value.trim();
}

function toNullableNumber(value: string) {
  return value === "" ? null : Number(value);
}

export default function TeachersPage() {
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [classes, setClasses] = useState<AcademicClass[]>([]);
  const [sections, setSections] = useState<Section[]>([]);
  const [sessions, setSessions] = useState<AcademicSession[]>([]);
  const [subjectAssignments, setSubjectAssignments] = useState<TeacherSubjectAssignment[]>([]);
  const [classTeacherAssignments, setClassTeacherAssignments] = useState<ClassTeacherAssignment[]>([]);
  const [form, setForm] = useState<TeacherForm>(emptyTeacherForm);
  const [subjectForm, setSubjectForm] = useState<SubjectForm>(emptySubjectForm);
  const [classTeacherForm, setClassTeacherForm] = useState<ClassTeacherForm>(emptyClassTeacherForm);
  const [editing, setEditing] = useState<Teacher | null>(null);
  const [search, setSearch] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [temporaryCredential, setTemporaryCredential] = useState("");

  const departmentById = useMemo(() => new Map(departments.map((item) => [item.id, item.name])), [departments]);
  const subjectById = useMemo(() => new Map(subjects.map((item) => [item.id, item.name])), [subjects]);
  const classById = useMemo(() => new Map(classes.map((item) => [item.id, item.name])), [classes]);
  const sectionById = useMemo(() => new Map(sections.map((item) => [item.id, item.name])), [sections]);
  const sectionLabel = (item: { section_id?: number | null; section_name?: string | null }) => item.section_name || (item.section_id ? sectionById.get(item.section_id) : "") || "";
  const sessionById = useMemo(() => new Map(sessions.map((item) => [item.id, item.name])), [sessions]);
  const teacherById = useMemo(() => new Map(teachers.map((item) => [item.id, item.full_name])), [teachers]);

  const subjectSections = useMemo(() => sections.filter((item) => !subjectForm.class_id || item.class_id === Number(subjectForm.class_id)), [sections, subjectForm.class_id]);
  const filteredSubjectsForAssignment = useMemo(() => subjects.filter((item) => subjectForm.class_id && item.class_id === Number(subjectForm.class_id)), [subjects, subjectForm.class_id]);
  const classTeacherSections = useMemo(() => sections.filter((item) => !classTeacherForm.class_id || item.class_id === Number(classTeacherForm.class_id)), [sections, classTeacherForm.class_id]);

  const setField = (name: keyof TeacherForm, value: string | boolean) => setForm((prev) => ({ ...prev, [name]: value }));
  const setSubjectField = (name: keyof SubjectForm, value: string) => setSubjectForm((prev) => ({ ...prev, [name]: value, ...(name === "class_id" ? { section_id: "", subject_id: "" } : {}) }));
  const setClassTeacherField = (name: keyof ClassTeacherForm, value: string) => setClassTeacherForm((prev) => ({ ...prev, [name]: value, ...(name === "class_id" ? { section_id: "" } : {}) }));

  const loadSetup = async () => {
    const [departmentData, subjectData, classData, sectionData, sessionData, classTeacherData] = await Promise.all([
      apiFetch<Department[]>("/departments"),
      apiFetch<Subject[]>("/subjects"),
      apiFetch<AcademicClass[]>("/classes"),
      apiFetch<Section[]>("/sections"),
      apiFetch<AcademicSession[]>("/academic-sessions"),
      apiFetch<ClassTeacherAssignment[]>("/teachers/class-teachers"),
    ]);
    setDepartments(departmentData);
    setSubjects(subjectData);
    setClasses(classData);
    setSections(sectionData);
    setSessions(sessionData);
    setClassTeacherAssignments(classTeacherData);
  };

  const loadTeachers = async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (departmentFilter) params.set("department_id", departmentFilter);
      const data = await apiFetch<Teacher[]>(`/teachers${params.toString() ? `?${params}` : ""}`);
      setTeachers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load teachers");
    } finally {
      setLoading(false);
    }
  };

  const loadTeacherSubjects = async (teacherId: string) => {
    if (!teacherId) {
      setSubjectAssignments([]);
      return;
    }
    const data = await apiFetch<TeacherSubjectAssignment[]>(`/teachers/${teacherId}/subjects`);
    setSubjectAssignments(data);
  };

  useEffect(() => {
    loadSetup().catch((err) => setError(err instanceof Error ? err.message : "Failed to load setup data"));
  }, []);

  useEffect(() => {
    loadTeachers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [departmentFilter]);

  useEffect(() => {
    loadTeacherSubjects(subjectForm.teacher_id).catch((err) => setError(err instanceof Error ? err.message : "Failed to load subject assignments"));
  }, [subjectForm.teacher_id]);

  const resetTeacher = () => {
    setForm(emptyTeacherForm);
    setEditing(null);
  };

  const buildTeacherPayload = () => ({
    employee_id: form.employee_id.trim(),
    full_name: form.full_name.trim(),
    email: toNullable(form.email),
    phone: toNullable(form.phone),
    gender: toNullable(form.gender),
    department_id: toNullableNumber(form.department_id),
    qualification: toNullable(form.qualification),
    specialization: toNullable(form.specialization),
    joining_date: toNullable(form.joining_date),
    photo_url: toNullable(form.photo_url),
    address: toNullable(form.address),
    create_login: form.create_login,
    password: form.create_login && form.password ? form.password : null,
  });

  const saveTeacher = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = buildTeacherPayload();
      setTemporaryCredential("");
      if (editing) {
        await apiFetch(`/teachers/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
      } else {
        const created = await apiFetch<Teacher>("/teachers", { method: "POST", body: JSON.stringify(payload) });
        if (created.temporary_password) {
          setTemporaryCredential(`Teacher login created. Login ID: ${created.employee_id}, temporary password: ${created.temporary_password}`);
        }
      }
      resetTeacher();
      await loadTeachers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Teacher save failed");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (teacher: Teacher) => {
    setEditing(teacher);
    setTemporaryCredential("");
    setForm({
      employee_id: teacher.employee_id ?? "",
      full_name: teacher.full_name ?? "",
      email: teacher.email ?? "",
      phone: teacher.phone ?? "",
      gender: teacher.gender ?? "",
      department_id: teacher.department_id ? String(teacher.department_id) : "",
      qualification: teacher.qualification ?? "",
      specialization: teacher.specialization ?? "",
      joining_date: teacher.joining_date ?? "",
      photo_url: teacher.photo_url ?? "",
      address: teacher.address ?? "",
      create_login: false,
      password: "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const deactivateTeacher = async (teacher: Teacher) => {
    if (!confirm(`Deactivate ${teacher.full_name}?`)) return;
    setError("");
    try {
      await apiFetch(`/teachers/${teacher.id}`, { method: "DELETE" });
      await loadTeachers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to deactivate teacher");
    }
  };

  const assignSubject = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await apiFetch(`/teachers/${subjectForm.teacher_id}/subjects`, {
        method: "POST",
        body: JSON.stringify({
          subject_id: Number(subjectForm.subject_id),
          class_id: Number(subjectForm.class_id),
          section_id: toNullableNumber(subjectForm.section_id),
        }),
      });
      await loadTeacherSubjects(subjectForm.teacher_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to assign subject");
    }
  };

  const removeSubjectAssignment = async (assignment: TeacherSubjectAssignment) => {
    if (!confirm("Remove this subject assignment?")) return;
    await apiFetch(`/teachers/subject-assignments/${assignment.id}`, { method: "DELETE" });
    await loadTeacherSubjects(subjectForm.teacher_id);
  };

  const assignClassTeacher = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await apiFetch("/teachers/class-teachers", {
        method: "POST",
        body: JSON.stringify({
          teacher_id: Number(classTeacherForm.teacher_id),
          class_id: Number(classTeacherForm.class_id),
          section_id: toNullableNumber(classTeacherForm.section_id),
          academic_session_id: toNullableNumber(classTeacherForm.academic_session_id),
        }),
      });
      setClassTeacherForm(emptyClassTeacherForm);
      const data = await apiFetch<ClassTeacherAssignment[]>("/teachers/class-teachers");
      setClassTeacherAssignments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to assign class teacher");
    }
  };

  const removeClassTeacherAssignment = async (assignment: ClassTeacherAssignment) => {
    if (!confirm("Remove this class teacher assignment?")) return;
    await apiFetch(`/teachers/class-teachers/${assignment.id}`, { method: "DELETE" });
    setClassTeacherAssignments(await apiFetch<ClassTeacherAssignment[]>("/teachers/class-teachers"));
  };

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Teachers</h1>
        <p className="mt-1 text-sm text-slate-500">Add teachers, create optional teacher login, assign subjects, and assign class teachers.</p>
      </div>

      <Card>
        <form onSubmit={saveTeacher} className="grid gap-4 md:grid-cols-3">
          <div>
            <Label>Employee ID *</Label>
            <Input value={form.employee_id} onChange={(e) => setField("employee_id", e.target.value)} required />
          </div>
          <div>
            <Label>Full Name *</Label>
            <Input value={form.full_name} onChange={(e) => setField("full_name", e.target.value)} required />
          </div>
          <div>
            <Label>Department</Label>
            <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={form.department_id} onChange={(e) => setField("department_id", e.target.value)}>
              <option value="">Select department</option>
              {departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </div>
          <div>
            <Label>Email</Label>
            <Input type="email" value={form.email} onChange={(e) => setField("email", e.target.value)} />
          </div>
          <div>
            <Label>Phone</Label>
            <Input value={form.phone} onChange={(e) => setField("phone", e.target.value)} />
          </div>
          <div>
            <Label>Gender</Label>
            <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={form.gender} onChange={(e) => setField("gender", e.target.value)}>
              <option value="">Select gender</option>
              <option>Male</option>
              <option>Female</option>
              <option>Other</option>
            </select>
          </div>
          <div>
            <Label>Qualification</Label>
            <Input value={form.qualification} onChange={(e) => setField("qualification", e.target.value)} />
          </div>
          <div>
            <Label>Specialization</Label>
            <Input value={form.specialization} onChange={(e) => setField("specialization", e.target.value)} placeholder="Maths, Physics, CS" />
          </div>
          <div>
            <Label>Joining Date</Label>
            <Input type="date" value={form.joining_date} onChange={(e) => setField("joining_date", e.target.value)} />
          </div>
          <div className="md:col-span-3">
            <Label>Photo URL</Label>
            <Input value={form.photo_url} onChange={(e) => setField("photo_url", e.target.value)} placeholder="Use Cloudinary/S3 URL for now" />
          </div>
          <div className="md:col-span-3">
            <Label>Address</Label>
            <Textarea value={form.address} onChange={(e) => setField("address", e.target.value)} />
          </div>
          {!editing && (
            <>
              <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm">
                <input type="checkbox" checked={form.create_login} onChange={(e) => setField("create_login", e.target.checked)} />
                Create teacher login account
              </label>
              {form.create_login && (
                <div>
                  <Label>Temporary Password</Label>
                  <Input type="password" value={form.password} onChange={(e) => setField("password", e.target.value)} minLength={6} placeholder="Auto-generate if blank" />
                  <p className="mt-1 text-xs text-slate-500">Teacher login ID will be the employee ID. User must change this password on first login.</p>
                </div>
              )}
            </>
          )}
          <div className="flex items-center gap-2 md:col-span-3">
            <Button disabled={saving} type="submit">
              <span className="inline-flex items-center gap-2"><UserPlus size={16} /> {editing ? "Update Teacher" : "Add Teacher"}</span>
            </Button>
            {editing && (
              <button type="button" onClick={resetTeacher} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100">
                <X size={16} /> Cancel
              </button>
            )}
          </div>
        </form>
        {temporaryCredential && <p className="mt-4 rounded-xl bg-green-50 px-3 py-2 text-sm text-green-800">{temporaryCredential}</p>}
        {error && <p className="mt-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      </Card>

      <Card className="mt-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <Label>Search teacher</Label>
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name, employee ID, phone" />
            </div>
            <div>
              <Label>Filter by department</Label>
              <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)}>
                <option value="">All departments</option>
                {departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
          </div>
          <Button type="button" onClick={loadTeachers}><span className="inline-flex items-center gap-2"><Search size={16} /> Search</span></Button>
        </div>

        <div className="mt-5 overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-100 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Teacher</th>
                <th className="px-4 py-3">Employee ID</th>
                <th className="px-4 py-3">Department</th>
                <th className="px-4 py-3">Specialization</th>
                <th className="px-4 py-3">Login</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr><td className="px-4 py-5 text-slate-500" colSpan={6}>Loading...</td></tr>
              ) : teachers.length === 0 ? (
                <tr><td className="px-4 py-5 text-slate-500" colSpan={6}>No teachers found.</td></tr>
              ) : teachers.map((teacher) => (
                <tr key={teacher.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full bg-slate-100 text-slate-400">
                        {teacher.photo_url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={fileUrl(teacher.photo_url)} alt={teacher.full_name} className="h-full w-full object-cover" />
                        ) : (
                          <UserRound size={18} />
                        )}
                      </div>
                      <div>
                        <p>{teacher.full_name}</p>
                        <p className="text-xs font-normal text-slate-500">{teacher.email || teacher.phone || "-"}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{teacher.employee_id}</td>
                  <td className="px-4 py-3 text-slate-600">{teacher.department_id ? departmentById.get(teacher.department_id) : "-"}</td>
                  <td className="px-4 py-3 text-slate-600">{teacher.specialization || "-"}</td>
                  <td className="px-4 py-3 text-slate-600">{teacher.user_id ? "Created" : "No login"}</td>
                  <td className="flex gap-2 px-4 py-3">
                    <button onClick={() => startEdit(teacher)} className="rounded-lg border border-slate-200 p-2 hover:bg-slate-100"><Edit2 size={15} /></button>
                    <button onClick={() => deactivateTeacher(teacher)} className="rounded-lg border border-red-200 p-2 text-red-600 hover:bg-red-50"><Trash2 size={15} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Card>
          <h2 className="mb-1 text-lg font-bold text-slate-900">Assign Teacher to Subject</h2>
          <p className="mb-4 text-sm text-slate-500">Select a teacher, class, subject, and optional section scope.</p>
          <form onSubmit={assignSubject} className="grid gap-3 md:grid-cols-2">
            <div>
              <Label>Teacher *</Label>
              <select required className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={subjectForm.teacher_id} onChange={(e) => setSubjectField("teacher_id", e.target.value)}>
                <option value="">Select teacher</option>
                {teachers.map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}
              </select>
            </div>
            <div>
              <Label>Class *</Label>
              <select required className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={subjectForm.class_id} onChange={(e) => setSubjectField("class_id", e.target.value)}>
                <option value="">Select class</option>
                {classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
            <div>
              <Label>Subject *</Label>
              <select required className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={subjectForm.subject_id} onChange={(e) => setSubjectField("subject_id", e.target.value)}>
                <option value="">{subjectForm.class_id ? "Select subject" : "Select class first"}</option>
                {filteredSubjectsForAssignment.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
            <div>
              <Label>Section</Label>
              <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={subjectForm.section_id} onChange={(e) => setSubjectField("section_id", e.target.value)}>
                <option value="">All / no section scope</option>
                {subjectSections.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
            <div className="md:col-span-2"><Button type="submit"><span className="inline-flex items-center gap-2"><Link2 size={16} /> Assign Subject</span></Button></div>
          </form>

          <div className="mt-4 space-y-2">
            {subjectAssignments.length === 0 ? <p className="text-sm text-slate-500">Select a teacher to view assignments.</p> : subjectAssignments.map((item) => (
              <div key={item.id} className="flex items-center justify-between rounded-xl border border-slate-200 p-3 text-sm">
                <span>{subjectById.get(item.subject_id) || item.subject_id} {item.class_id ? `• ${classById.get(item.class_id)}` : ""} {sectionLabel(item) ? `• ${sectionLabel(item)}` : ""}</span>
                <button onClick={() => removeSubjectAssignment(item)} className="text-red-600 hover:underline">Remove</button>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="mb-1 text-lg font-bold text-slate-900">Assign Class Teacher</h2>
          <p className="mb-4 text-sm text-slate-500">Each class/section/session can have one class teacher.</p>
          <form onSubmit={assignClassTeacher} className="grid gap-3 md:grid-cols-2">
            <div>
              <Label>Teacher *</Label>
              <select required className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={classTeacherForm.teacher_id} onChange={(e) => setClassTeacherField("teacher_id", e.target.value)}>
                <option value="">Select teacher</option>
                {teachers.map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}
              </select>
            </div>
            <div>
              <Label>Class *</Label>
              <select required className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={classTeacherForm.class_id} onChange={(e) => setClassTeacherField("class_id", e.target.value)}>
                <option value="">Select class</option>
                {classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
            <div>
              <Label>Section</Label>
              <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={classTeacherForm.section_id} onChange={(e) => setClassTeacherField("section_id", e.target.value)}>
                <option value="">All sections</option>
                {classTeacherSections.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
            <div>
              <Label>Academic Session</Label>
              <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm" value={classTeacherForm.academic_session_id} onChange={(e) => setClassTeacherField("academic_session_id", e.target.value)}>
                <option value="">Current / no session</option>
                {sessions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </div>
            <div className="md:col-span-2"><Button type="submit"><span className="inline-flex items-center gap-2"><Link2 size={16} /> Assign Class Teacher</span></Button></div>
          </form>

          <div className="mt-4 space-y-2">
            {classTeacherAssignments.length === 0 ? <p className="text-sm text-slate-500">No class teacher assignments yet.</p> : classTeacherAssignments.map((item) => (
              <div key={item.id} className="flex items-center justify-between rounded-xl border border-slate-200 p-3 text-sm">
                <span>{teacherById.get(item.teacher_id) || item.teacher_id} → {classById.get(item.class_id) || item.class_id} {sectionLabel(item) ? `• ${sectionLabel(item)}` : ""} {item.academic_session_id ? `• ${sessionById.get(item.academic_session_id)}` : ""}</span>
                <button onClick={() => removeClassTeacherAssignment(item)} className="text-red-600 hover:underline">Remove</button>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
