"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  Mail,
  Phone,
  Save,
  Search,
  Upload,
  ShieldCheck,
  UserRound,
  Users,
} from "lucide-react";

import AppShell from "@/components/AppShell";
import { ACADEMIC_SESSION_CHANGED_EVENT, apiFetch, apiUpload, fileUrl, updateSavedAuthUser } from "@/lib/api";

type AnyRecord = Record<string, any>;

type ProfileResponse = {
  account: {
    id: number;
    full_name: string;
    email?: string | null;
    phone?: string | null;
    login_id?: string | null;
    role: string;
  };
  school?: {
    id: number;
    name: string;
    school_code?: string | null;
    institution_type?: string | null;
  } | null;
  editable_fields: string[];
  summary: AnyRecord;
  role_data: AnyRecord;
};

type StudentItem = {
  id: number;
  name: string;
  admission_no?: string | null;
  roll_number?: string | null;
  email?: string | null;
  phone?: string | null;
  class_id?: number | null;
  class_name?: string | null;
  section_id?: number | null;
  section_name?: string | null;
  status?: string | null;
  is_active?: boolean;
  class_teachers?: AnyRecord[];
  subject_teachers?: AnyRecord[];
};

const ADMIN_ROLES = new Set(["SUPER_ADMIN", "SCHOOL_OWNER", "SCHOOL_ADMIN"]);

function formatRole(value?: string | null) {
  return String(value || "")
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function fieldLabel(field: string) {
  const labels: Record<string, string> = {
    full_name: "Name",
    email: "Email",
    phone: "Phone",
    alternate_phone: "Alternate Phone",
    occupation: "Occupation",
    address: "Address",
    photo_url: "Photo URL",
  };
  return labels[field] || field.replaceAll("_", " ");
}

function safeValue(value?: string | number | null) {
  return value === undefined || value === null || value === "" ? "—" : String(value);
}

function detailValue(profile: ProfileResponse, field: string) {
  const role = profile.account.role;
  if (ADMIN_ROLES.has(role)) return profile.account[field as keyof ProfileResponse["account"]] || "";
  if (role === "STUDENT") return profile.role_data?.student?.[field] || "";
  if (role === "TEACHER") return profile.role_data?.teacher?.[field] || "";
  if (role === "PARENT") return profile.role_data?.guardian?.[field] || profile.account[field as keyof ProfileResponse["account"]] || "";
  return profile.account[field as keyof ProfileResponse["account"]] || "";
}

function InfoCard({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 wrap-break-word text-sm font-semibold text-slate-900">{safeValue(value)}</p>
    </div>
  );
}

function SectionCard({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-slate-950">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function EmptyBox({ text }: { text: string }) {
  return <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-500">{text}</div>;
}

function Pill({ children }: { children: React.ReactNode }) {
  return <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">{children}</span>;
}

function StudentTable({ students, search }: { students: StudentItem[]; search: string }) {
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return students;
    return students.filter((student) =>
      [student.name, student.admission_no, student.roll_number, student.email, student.phone, student.section_name, student.status]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(q)),
    );
  }, [students, search]);

  if (!students.length) return <EmptyBox text="No students found for this class/section." />;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200">
      <div className="max-h-80 overflow-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="sticky top-0 bg-slate-50">
            <tr className="text-left text-xs font-bold uppercase tracking-wide text-slate-500">
              <th className="px-4 py-3">Student</th>
              <th className="px-4 py-3">Admission</th>
              <th className="px-4 py-3">Section</th>
              <th className="px-4 py-3">Contact</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {filtered.map((student) => (
              <tr key={student.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <p className="font-semibold text-slate-900">{student.name}</p>
                  <p className="text-xs text-slate-500">Roll: {safeValue(student.roll_number)}</p>
                </td>
                <td className="px-4 py-3 text-slate-700">{safeValue(student.admission_no)}</td>
                <td className="px-4 py-3 text-slate-700">{safeValue(student.section_name)}</td>
                <td className="px-4 py-3 text-slate-700">
                  <div className="space-y-1">
                    {student.email && <p className="flex items-center gap-1"><Mail size={13} /> {student.email}</p>}
                    {student.phone && <p className="flex items-center gap-1"><Phone size={13} /> {student.phone}</p>}
                    {!student.email && !student.phone && "—"}
                  </div>
                </td>
                <td className="px-4 py-3"><Pill>{student.status || "ACTIVE"}</Pill></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length === 0 && <div className="border-t border-slate-100 p-4 text-sm text-slate-500">No student matches this search.</div>}
    </div>
  );
}

function TeacherPhotoUploader({ profile, onSaved }: { profile: ProfileResponse; onSaved: (profile: ProfileResponse) => void }) {
  const teacher = profile.role_data?.teacher;
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  if (profile.account.role !== "TEACHER" || !teacher) return null;

  const photoUrl = fileUrl(teacher.photo_url);

  const uploadPhoto = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMessage(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const updated = await apiUpload<ProfileResponse>("/profile/teacher/photo", formData, { method: "POST" });
      onSaved(updated);
      // Persist the new photo_url into saved auth so navbar/sidebar update immediately
      if (updated.role_data?.teacher?.photo_url) {
        updateSavedAuthUser({ photo_url: updated.role_data.teacher.photo_url });
      }
      setMessage("Profile photo updated successfully.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to upload profile photo.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  return (
    <SectionCard title="Teacher Profile Picture">
      <div className="flex flex-wrap items-center gap-5">
        <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-full border border-slate-200 bg-slate-100">
          {photoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={photoUrl} alt="Teacher profile" className="h-full w-full object-cover" />
          ) : (
            <UserRound size={38} className="text-slate-400" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-slate-800">Upload PNG, JPG, JPEG, or WEBP image up to 3 MB.</p>
          <p className="mt-1 text-sm text-slate-500">The uploaded teacher photo is stored on Cloudinary and saved in the teacher profile record.</p>
          <label className="mt-4 inline-flex cursor-pointer items-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-bold text-white shadow-sm hover:bg-slate-800">
            <Upload size={16} /> {uploading ? "Uploading..." : photoUrl ? "Change Photo" : "Upload Photo"}
            <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={uploadPhoto} disabled={uploading} />
          </label>
          {message && <p className="mt-3 text-sm font-medium text-slate-600">{message}</p>}
        </div>
      </div>
    </SectionCard>
  );
}

function EditableProfile({ profile, onSaved }: { profile: ProfileResponse; onSaved: (profile: ProfileResponse) => void }) {
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const next: Record<string, string> = {};
    profile.editable_fields.forEach((field) => {
      next[field] = String(detailValue(profile, field) || "");
    });
    setForm(next);
    setMessage(null);
  }, [profile]);

  const save = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const payload = Object.fromEntries(profile.editable_fields.map((field) => [field, form[field] ?? ""]));
      const updated = await apiFetch<ProfileResponse>("/profile", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      onSaved(updated);
      setMessage("Profile updated successfully.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to update profile.");
    } finally {
      setSaving(false);
    }
  };

  if (!profile.editable_fields.length) return null;

  return (
    <SectionCard title="Editable Details">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {profile.editable_fields.map((field) => (
          <label key={field} className={field === "address" ? "md:col-span-2 xl:col-span-3" : ""}>
            <span className="text-sm font-semibold text-slate-700">{fieldLabel(field)}</span>
            {field === "address" ? (
              <textarea
                value={form[field] || ""}
                onChange={(event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))}
                className="mt-2 min-h-24 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-slate-400"
              />
            ) : (
              <input
                value={form[field] || ""}
                onChange={(event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))}
                className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-slate-400"
              />
            )}
          </label>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-bold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Save size={16} /> {saving ? "Saving..." : "Save Profile"}
        </button>
        {message && <p className="text-sm font-medium text-slate-600">{message}</p>}
      </div>
      <p className="mt-3 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
        Login ID, role, admission number, employee ID, class, section and subject assignments are locked here. Admin pages should be used for those changes.
      </p>
    </SectionCard>
  );
}

function AccountOverview({ profile }: { profile: ProfileResponse }) {
  const role = profile.account.role;
  const student = profile.role_data?.student;
  const teacher = profile.role_data?.teacher;
  const guardian = profile.role_data?.guardian;

  return (
    <SectionCard title="Account Information">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <InfoCard label="Name" value={profile.account.full_name} />
        <InfoCard label="Email" value={profile.account.email} />
        <InfoCard label="Phone" value={profile.account.phone} />
        <InfoCard label="Login ID" value={profile.account.login_id} />
        <InfoCard label="Role" value={formatRole(role)} />
        {student && <InfoCard label="Admission No" value={student.admission_no} />}
        {student && <InfoCard label="Class" value={`${safeValue(student.class_name)} - ${safeValue(student.section_name)}`} />}
        {teacher && <InfoCard label="Employee ID" value={teacher.employee_id} />}
        {teacher && <InfoCard label="Specialization" value={teacher.specialization} />}
        {guardian && <InfoCard label="Guardian Name" value={guardian.full_name} />}
        {guardian && <InfoCard label="Children" value={profile.role_data?.children_count ?? 0} />}
      </div>
    </SectionCard>
  );
}

function StudentProfile({ data }: { data: AnyRecord }) {
  const student = data.student;
  if (!student) return <EmptyBox text={data.message || "Student profile not linked yet."} />;
  return (
    <div className="space-y-6">
      <SectionCard title="Student Details">
        <div className="grid gap-4 md:grid-cols-3">
          <InfoCard label="Student Name" value={student.name} />
          <InfoCard label="Admission No" value={student.admission_no} />
          <InfoCard label="Class" value={`${safeValue(student.class_name)} - ${safeValue(student.section_name)}`} />
          <InfoCard label="Email" value={student.email} />
          <InfoCard label="Phone" value={student.phone} />
          <InfoCard label="Address" value={student.address} />
        </div>
      </SectionCard>
      <SectionCard title="Class Teacher">
        {data.class_teachers?.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {data.class_teachers.map((item: AnyRecord) => (
              <div key={item.id} className="rounded-2xl border border-slate-200 p-4">
                <p className="font-bold text-slate-950">{safeValue(item.teacher_name)}</p>
                <p className="text-sm text-slate-500">{safeValue(item.class_name)} · {safeValue(item.section_name)}</p>
                <p className="mt-1 text-xs text-slate-400">Session: {safeValue(item.academic_session_name)}</p>
              </div>
            ))}
          </div>
        ) : <EmptyBox text="No class teacher assigned yet." />}
      </SectionCard>
      <SectionCard title="Subject Teachers">
        {data.subject_teachers?.length ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {data.subject_teachers.map((item: AnyRecord) => (
              <div key={item.id} className="rounded-2xl border border-slate-200 p-4">
                <p className="font-bold text-slate-950">{safeValue(item.subject_name)}</p>
                <p className="text-sm text-slate-600">Teacher: {safeValue(item.teacher_name)}</p>
                <p className="mt-1 text-xs text-slate-400">{safeValue(item.class_name)} · {safeValue(item.section_name)}</p>
              </div>
            ))}
          </div>
        ) : <EmptyBox text="No subject teacher assignment found yet." />}
      </SectionCard>
    </div>
  );
}

function ParentProfile({ data }: { data: AnyRecord }) {
  const children: StudentItem[] = data.children || [];
  return (
    <div className="space-y-6">
      <SectionCard title="Parent / Guardian Details">
        {data.guardian ? (
          <div className="grid gap-4 md:grid-cols-3">
            <InfoCard label="Name" value={data.guardian.full_name} />
            <InfoCard label="Email" value={data.guardian.email} />
            <InfoCard label="Phone" value={data.guardian.phone} />
            <InfoCard label="Alternate Phone" value={data.guardian.alternate_phone} />
            <InfoCard label="Occupation" value={data.guardian.occupation} />
            <InfoCard label="Address" value={data.guardian.address} />
          </div>
        ) : <EmptyBox text={data.message || "No guardian profile linked yet."} />}
      </SectionCard>
      <SectionCard title={`My Children (${children.length})`}>
        {children.length ? (
          <div className="grid gap-4">
            {children.map((child) => (
              <div key={child.id} className="rounded-3xl border border-slate-200 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-bold text-slate-950">{child.name}</h3>
                    <p className="text-sm text-slate-500">Admission: {safeValue(child.admission_no)} · Class {safeValue(child.class_name)} - {safeValue(child.section_name)}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {child.email && <Pill><Mail size={13} className="mr-1" /> {child.email}</Pill>}
                    {child.phone && <Pill><Phone size={13} className="mr-1" /> {child.phone}</Pill>}
                  </div>
                </div>
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <div>
                    <h4 className="mb-2 text-sm font-bold text-slate-800">Class Teacher</h4>
                    {child.class_teachers?.length ? child.class_teachers.map((item) => (
                      <div key={item.id} className="rounded-2xl border border-slate-100 bg-slate-50 p-3 text-sm">
                        <p className="font-semibold text-slate-900">{safeValue(item.teacher_name)}</p>
                        <p className="text-slate-500">{safeValue(item.academic_session_name)}</p>
                      </div>
                    )) : <EmptyBox text="No class teacher assigned." />}
                  </div>
                  <div>
                    <h4 className="mb-2 text-sm font-bold text-slate-800">Subject Teachers</h4>
                    {child.subject_teachers?.length ? (
                      <div className="grid gap-2">
                        {child.subject_teachers.map((item) => <Pill key={item.id}>{safeValue(item.subject_name)}: {safeValue(item.teacher_name)}</Pill>)}
                      </div>
                    ) : <EmptyBox text="No subject teacher assignment found yet." />}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : <EmptyBox text="No child is linked to this parent login. Ask admin to link the correct guardian record." />}
      </SectionCard>
    </div>
  );
}

function TeacherProfile({ data }: { data: AnyRecord }) {
  const [openClass, setOpenClass] = useState<Record<string, boolean>>({});
  const [search, setSearch] = useState("");
  const teacher = data.teacher;
  const classes = data.assigned_classes || [];

  if (!teacher) return <EmptyBox text={data.message || "Teacher profile not linked yet."} />;

  return (
    <div className="space-y-6">
      <SectionCard title="Teacher Details">
        <div className="grid gap-4 md:grid-cols-3">
          <InfoCard label="Teacher Name" value={teacher.name} />
          <InfoCard label="Employee ID" value={teacher.employee_id} />
          <InfoCard label="Specialization" value={teacher.specialization} />
          <InfoCard label="Email" value={teacher.email} />
          <InfoCard label="Phone" value={teacher.phone} />
          <InfoCard label="Address" value={teacher.address} />
        </div>
      </SectionCard>
      <SectionCard title="Assigned Subjects">
        {data.subject_assignments?.length ? (
          <div className="flex flex-wrap gap-2">
            {data.subject_assignments.map((item: AnyRecord) => (
              <Pill key={item.id}>{safeValue(item.subject_name)} · {safeValue(item.class_name)} - {safeValue(item.section_name)}</Pill>
            ))}
          </div>
        ) : <EmptyBox text="No subject assigned yet." />}
      </SectionCard>
      <SectionCard
        title="My Classes"
        action={
          <div className="relative w-full sm:w-72">
            <Search size={16} className="absolute left-3 top-3 text-slate-400" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search students..."
              className="w-full rounded-2xl border border-slate-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-slate-400"
            />
          </div>
        }
      >
        {classes.length ? (
          <div className="space-y-3">
            {classes.map((item: AnyRecord) => {
              const key = `${item.class_id}-${item.section_name || item.section_id || "all"}`;
              const open = Boolean(openClass[key]);
              return (
                <div key={key} className="rounded-2xl border border-slate-200">
                  <button
                    type="button"
                    onClick={() => setOpenClass((prev) => ({ ...prev, [key]: !prev[key] }))}
                    className="flex w-full items-center justify-between gap-4 p-4 text-left"
                  >
                    <div>
                      <p className="font-bold text-slate-950">{safeValue(item.class_name)} - {safeValue(item.section_name)}</p>
                      <p className="text-sm text-slate-500">{item.total_students || 0} students</p>
                    </div>
                    {open ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                  </button>
                  {open && <div className="border-t border-slate-100 p-4"><StudentTable students={item.students || []} search={search} /></div>}
                </div>
              );
            })}
          </div>
        ) : <EmptyBox text="No class or section assigned yet." />}
      </SectionCard>
    </div>
  );
}

function AdminProfile({ profile }: { profile: ProfileResponse }) {
  const [openClass, setOpenClass] = useState<Record<string, boolean>>({});
  const [studentSearch, setStudentSearch] = useState("");
  const [classSearch, setClassSearch] = useState("");
  const classes = profile.role_data?.classes || [];
  const filteredClasses = classes.filter((item: AnyRecord) => String(item.name || "").toLowerCase().includes(classSearch.toLowerCase()));

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <SectionCard title="Students"><p className="text-3xl font-black text-slate-950">{profile.summary?.students ?? 0}</p></SectionCard>
        <SectionCard title="Teachers"><p className="text-3xl font-black text-slate-950">{profile.summary?.teachers ?? 0}</p></SectionCard>
        <SectionCard title="Parents"><p className="text-3xl font-black text-slate-950">{profile.summary?.parents ?? 0}</p></SectionCard>
        <SectionCard title="Classes"><p className="text-3xl font-black text-slate-950">{profile.summary?.classes ?? 0}</p></SectionCard>
        <SectionCard title="Subjects"><p className="text-3xl font-black text-slate-950">{profile.summary?.subjects ?? 0}</p></SectionCard>
      </div>
      <SectionCard
        title="Class-wise Students, Class Teachers & Subject Teachers"
        action={
          <div className="grid w-full gap-2 sm:w-auto sm:grid-cols-2">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-3 text-slate-400" />
              <input
                value={classSearch}
                onChange={(event) => setClassSearch(event.target.value)}
                placeholder="Search class..."
                className="w-full rounded-2xl border border-slate-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-slate-400"
              />
            </div>
            <div className="relative">
              <Search size={16} className="absolute left-3 top-3 text-slate-400" />
              <input
                value={studentSearch}
                onChange={(event) => setStudentSearch(event.target.value)}
                placeholder="Search students..."
                className="w-full rounded-2xl border border-slate-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-slate-400"
              />
            </div>
          </div>
        }
      >
        {filteredClasses.length ? (
          <div className="space-y-3">
            {filteredClasses.map((item: AnyRecord) => {
              const open = Boolean(openClass[item.id]);
              return (
                <div key={item.id} className="rounded-3xl border border-slate-200 bg-white">
                  <button
                    type="button"
                    onClick={() => setOpenClass((prev) => ({ ...prev, [item.id]: !prev[item.id] }))}
                    className="flex w-full flex-wrap items-center justify-between gap-4 p-5 text-left"
                  >
                    <div>
                      <h3 className="text-lg font-bold text-slate-950">{item.name}</h3>
                      <p className="text-sm text-slate-500">{item.total_students || 0} students · {item.sections?.length || 0} sections</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Pill>{item.class_teachers?.length || 0} class teachers</Pill>
                      <Pill>{item.subject_teachers?.length || 0} subject teachers</Pill>
                      {open ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                    </div>
                  </button>
                  {open && (
                    <div className="space-y-4 border-t border-slate-100 p-5">
                      <div className="grid gap-4 lg:grid-cols-2">
                        <div className="rounded-2xl bg-slate-50 p-4">
                          <h4 className="mb-2 text-sm font-bold text-slate-800">Class Teachers</h4>
                          {item.class_teachers?.length ? (
                            <div className="flex flex-wrap gap-2">
                              {item.class_teachers.map((teacher: AnyRecord) => (
                                <Pill key={teacher.id}>{safeValue(teacher.teacher_name)} · {safeValue(teacher.section_name)}</Pill>
                              ))}
                            </div>
                          ) : <p className="text-sm text-slate-500">Not assigned.</p>}
                        </div>
                        <div className="rounded-2xl bg-slate-50 p-4">
                          <h4 className="mb-2 text-sm font-bold text-slate-800">Subject Teachers</h4>
                          {item.subject_teachers?.length ? (
                            <div className="flex flex-wrap gap-2">
                              {item.subject_teachers.map((teacher: AnyRecord) => (
                                <Pill key={teacher.id}>{safeValue(teacher.subject_name)}: {safeValue(teacher.teacher_name)} · {safeValue(teacher.section_name)}</Pill>
                              ))}
                            </div>
                          ) : <p className="text-sm text-slate-500">Not assigned.</p>}
                        </div>
                      </div>
                      <StudentTable students={item.students || []} search={studentSearch} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : <EmptyBox text="No class matches this filter." />}
      </SectionCard>
    </div>
  );
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProfile(await apiFetch<ProfileResponse>("/profile"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load profile.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  useEffect(() => {
    const onSessionChanged = () => {
      loadProfile();
    };
    window.addEventListener(ACADEMIC_SESSION_CHANGED_EVENT, onSessionChanged);
    return () => window.removeEventListener(ACADEMIC_SESSION_CHANGED_EVENT, onSessionChanged);
  }, [loadProfile]);

  const content = useMemo(() => {
    if (!profile) return null;
    if (profile.account.role === "STUDENT") return <StudentProfile data={profile.role_data} />;
    if (profile.account.role === "TEACHER") return <TeacherProfile data={profile.role_data} />;
    if (profile.account.role === "PARENT") return <ParentProfile data={profile.role_data} />;
    return <AdminProfile profile={profile} />;
  }, [profile]);

  return (
    <AppShell>
      {loading && <div className="rounded-3xl border border-slate-200 bg-white p-8 text-slate-600 shadow-sm">Loading profile...</div>}
      {!loading && error && <div className="rounded-3xl border border-red-200 bg-red-50 p-8 text-red-700 shadow-sm">{error}</div>}
      {!loading && profile && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-slate-400"><ShieldCheck size={16} /> My Profile</p>
              <h1 className="mt-2 text-3xl font-black text-slate-950">{profile.account.full_name}</h1>
              <p className="mt-1 text-slate-500">{formatRole(profile.account.role)} · Login ID: {profile.account.login_id}</p>
              {profile.summary?.academic_session_name && (
                <p className="mt-1 text-sm font-semibold text-slate-600">Selected Session: {profile.summary.academic_session_name}</p>
              )}
            </div>
            {profile.school && (
              <div className="rounded-3xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
                <p className="font-bold text-slate-950">{profile.school.name}</p>
                <p className="text-sm text-slate-500">School Code: {profile.school.school_code}</p>
              </div>
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <UserRound className="mb-3 text-slate-500" size={24} />
              <p className="text-sm text-slate-500">Account Role</p>
              <p className="text-xl font-black text-slate-950">{formatRole(profile.account.role)}</p>
            </div>
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <Users className="mb-3 text-slate-500" size={24} />
              <p className="text-sm text-slate-500">Linked Records</p>
              <p className="text-xl font-black text-slate-950">
                {profile.account.role === "PARENT" ? `${profile.role_data?.children_count || 0} Children` : profile.account.role === "TEACHER" ? `${profile.role_data?.assigned_classes?.length || 0} Classes` : profile.account.role === "STUDENT" ? "1 Student" : `${profile.summary?.students || 0} Students`}
              </p>
            </div>
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <BookOpen className="mb-3 text-slate-500" size={24} />
              <p className="text-sm text-slate-500">Academic View</p>
              <p className="text-xl font-black text-slate-950">
                {ADMIN_ROLES.has(profile.account.role) ? `${profile.summary?.classes || 0} Classes` : "Role Based"}
              </p>
            </div>
          </div>

          <TeacherPhotoUploader profile={profile} onSaved={setProfile} />
          <EditableProfile profile={profile} onSaved={setProfile} />
          <AccountOverview profile={profile} />
          {content}
        </div>
      )}
    </AppShell>
  );
}
