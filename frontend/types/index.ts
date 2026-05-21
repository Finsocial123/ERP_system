export type User = {
  id: number;
  full_name: string;
  email?: string | null;
  phone?: string | null;
  login_id?: string | null;
  role: string;
  school_id?: number | null;
  must_change_password?: boolean;
};

export type School = {
  id: number;
  name: string;
  slug: string;
  school_code: string;
  institution_type: string;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  logo_url?: string | null;
  is_active?: boolean;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
  school?: School | null;
};

export type FieldConfig = {
  name: string;
  label: string;
  type?: "text" | "number" | "date" | "checkbox" | "textarea";
  placeholder?: string;
  required?: boolean;
};

export type AcademicClass = {
  id: number;
  name: string;
  code?: string | null;
  department_id?: number | null;
  is_active: boolean;
};

export type Section = {
  id: number;
  name: string;
  class_id: number;
  is_active: boolean;
};

export type Subject = {
  id: number;
  name: string;
  code?: string | null;
  department_id?: number | null;
  class_id?: number | null;
  is_active: boolean;
};

export type Department = {
  id: number;
  name: string;
  code?: string | null;
  description?: string | null;
  is_active: boolean;
};

export type AcademicSession = {
  id: number;
  name: string;
  start_date?: string | null;
  end_date?: string | null;
  is_active: boolean;
};

export type ParentGuardian = {
  id: number;
  full_name: string;
  relation?: string | null;
  email?: string | null;
  phone?: string | null;
  alternate_phone?: string | null;
  occupation?: string | null;
  address?: string | null;
  is_active: boolean;
};

export type Student = {
  id: number;
  admission_no: string;
  roll_number?: string | null;
  first_name: string;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  gender?: string | null;
  date_of_birth?: string | null;
  blood_group?: string | null;
  photo_url?: string | null;
  address?: string | null;
  admission_date?: string | null;
  class_id?: number | null;
  section_id?: number | null;
  guardian?: ParentGuardian | null;
  status: string;
  is_active: boolean;
  user_id?: number | null;
  temporary_password?: string | null;
};

export type Teacher = {
  id: number;
  employee_id: string;
  full_name: string;
  email?: string | null;
  phone?: string | null;
  gender?: string | null;
  department_id?: number | null;
  qualification?: string | null;
  specialization?: string | null;
  joining_date?: string | null;
  photo_url?: string | null;
  address?: string | null;
  status: string;
  is_active: boolean;
  user_id?: number | null;
  temporary_password?: string | null;
};

export type TeacherSubjectAssignment = {
  id: number;
  teacher_id: number;
  subject_id: number;
  class_id?: number | null;
  section_id?: number | null;
};

export type ClassTeacherAssignment = {
  id: number;
  teacher_id: number;
  class_id: number;
  section_id?: number | null;
  academic_session_id?: number | null;
};
