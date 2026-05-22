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


export type AttendanceRecord = {
  id: number;
  student_id: number;
  class_id: number;
  section_id?: number | null;
  session_id: number;
  date: string;
  status: string;
  note?: string | null;
  marked_by?: number | null;
};

export type AttendanceSummary = {
  student_id: number;
  student_name: string;
  admission_no: string;
  total_days: number;
  present: number;
  absent: number;
  leave: number;
  half_day: number;
  percentage: number;
  low_attendance: boolean;
};


export type HomeworkMetaItem = {
  id: number;
  name: string;
  extra?: string | null;
};

export type HomeworkMeta = {
  classes: HomeworkMetaItem[];
  sections: HomeworkMetaItem[];
  subjects: HomeworkMetaItem[];
  teachers: HomeworkMetaItem[];
  current_academic_session_id?: number | null;
};

export type HomeworkStats = {
  total_students: number;
  pending: number;
  submitted: number;
  checked: number;
};

export type HomeworkAssignment = {
  id: number;
  title: string;
  description?: string | null;
  due_date: string;
  class_id: number;
  section_id?: number | null;
  subject_id?: number | null;
  teacher_id?: number | null;
  academic_session_id?: number | null;
  class_name?: string | null;
  section_name?: string | null;
  subject_name?: string | null;
  teacher_name?: string | null;
  attachment_url?: string | null;
  attachment_filename?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  stats: HomeworkStats;
};

export type StudentHomework = HomeworkAssignment & {
  submission_id?: number | null;
  submission_status: "PENDING" | "SUBMITTED" | "CHECKED" | string;
  submitted_at?: string | null;
  answer_text?: string | null;
  submission_attachment_url?: string | null;
  submission_attachment_filename?: string | null;
  teacher_feedback?: string | null;
  checked_at?: string | null;
};

export type ParentHomework = StudentHomework & {
  student_id: number;
  student_name: string;
  admission_no: string;
};

export type HomeworkSubmission = {
  id?: number | null;
  homework_id: number;
  student_id: number;
  student_name: string;
  admission_no: string;
  roll_number?: string | null;
  status: "PENDING" | "SUBMITTED" | "CHECKED" | string;
  answer_text?: string | null;
  attachment_url?: string | null;
  attachment_filename?: string | null;
  teacher_feedback?: string | null;
  submitted_at?: string | null;
  checked_at?: string | null;
};

export type TimetablePeriod = {
  id: number;
  period_number: number;
  name: string;
  start_time?: string | null;
  end_time?: string | null;
  is_break: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type TimetableDay = {
  id: number;
  day_of_week: string;
  display_name: string;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type TimetableMetaItem = {
  id: number;
  name: string;
  extra?: string | null;
};

export type TimetableMeta = {
  classes: TimetableMetaItem[];
  sections: TimetableMetaItem[];
  subjects: TimetableMetaItem[];
  teachers: TimetableMetaItem[];
  periods: TimetablePeriod[];
  days: TimetableDay[];
  academic_sessions: TimetableMetaItem[];
  current_academic_session_id?: number | null;
};

export type TimetableEntry = {
  id: number;
  class_id: number;
  section_id?: number | null;
  day_id: number;
  period_id: number;
  subject_id?: number | null;
  teacher_id?: number | null;
  room?: string | null;
  note?: string | null;
  academic_session_id?: number | null;
  is_active: boolean;
  class_name?: string | null;
  section_name?: string | null;
  day_name?: string | null;
  day_of_week?: string | null;
  day_sort_order?: number | null;
  period_name?: string | null;
  period_number?: number | null;
  start_time?: string | null;
  end_time?: string | null;
  subject_name?: string | null;
  teacher_name?: string | null;
  academic_session_name?: string | null;
  created_at: string;
  updated_at: string;
};

export type TimetableGrid = {
  mode: string;
  title: string;
  entries: TimetableEntry[];
  periods: TimetablePeriod[];
  days: TimetableDay[];
};

export type ExamMetaItem = {
  id: number;
  name: string;
  extra?: string | null;
};

export type ExamMeta = {
  classes: ExamMetaItem[];
  sections: ExamMetaItem[];
  subjects: ExamMetaItem[];
  teachers: ExamMetaItem[];
  academic_sessions: ExamMetaItem[];
  current_academic_session_id?: number | null;
};

export type Exam = {
  id: number;
  name: string;
  exam_type?: string | null;
  description?: string | null;
  class_id: number;
  section_id?: number | null;
  academic_session_id?: number | null;
  class_name?: string | null;
  section_name?: string | null;
  academic_session_name?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  result_status: "DRAFT" | "PUBLISHED" | string;
  is_active: boolean;
  subjects_count: number;
  marks_entered_count: number;
  created_at: string;
  updated_at: string;
  published_at?: string | null;
};

export type ExamSubject = {
  id: number;
  exam_id: number;
  subject_id: number;
  teacher_id?: number | null;
  subject_name?: string | null;
  teacher_name?: string | null;
  max_marks: number;
  pass_marks: number;
  exam_date?: string | null;
  is_active: boolean;
  marks_entered_count: number;
  created_at: string;
  updated_at: string;
};

export type ExamStudent = {
  id: number;
  admission_no: string;
  roll_number?: string | null;
  student_name: string;
  class_name?: string | null;
  section_name?: string | null;
};

export type ExamMark = {
  id?: number | null;
  exam_subject_id: number;
  student_id: number;
  student_name: string;
  admission_no: string;
  roll_number?: string | null;
  marks_obtained?: number | null;
  max_marks: number;
  pass_marks: number;
  grade?: string | null;
  is_absent: boolean;
  pass_status: "PENDING" | "PASS" | "FAIL" | "ABSENT" | string;
  remarks?: string | null;
  updated_at?: string | null;
};

export type ReportCardSubject = {
  exam_subject_id: number;
  subject_id: number;
  subject_name: string;
  max_marks: number;
  pass_marks: number;
  marks_obtained?: number | null;
  grade?: string | null;
  is_absent: boolean;
  pass_status: string;
  remarks?: string | null;
};

export type StudentReportCard = {
  exam_id: number;
  exam_name: string;
  exam_type?: string | null;
  result_status: string;
  student_id: number;
  student_name: string;
  admission_no: string;
  roll_number?: string | null;
  class_name?: string | null;
  section_name?: string | null;
  subjects: ReportCardSubject[];
  total_marks: number;
  marks_obtained: number;
  percentage: number;
  grade: string;
  pass_status: string;
  published_at?: string | null;
};

export type ClassResult = {
  exam: Exam;
  results: StudentReportCard[];
  summary: Record<string, number | string>;
};

export type SubjectResult = {
  exam: Exam;
  exam_subject: ExamSubject;
  results: ExamMark[];
  summary: Record<string, number | string>;
};
