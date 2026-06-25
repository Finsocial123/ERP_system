export type User = {
    id: number;
    full_name: string;
    email?: string | null;
    phone?: string | null;
    login_id?: string | null;
    role: string;
    school_id?: number | null;
    must_change_password?: boolean;
    photo_url?: string | null;
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


  export type SchoolBranding = {
    id: number;
    school_id: number;
    logo_url?: string | null;
    favicon_url?: string | null;
    primary_color: string;
    secondary_color: string;
    accent_color: string;
    sidebar_color: string;
    background_color: string;
    text_color: string;
    theme_mode: "light" | "dark" | "auto" | string;
    theme_source: "preset" | "manual" | "logo_generated" | string;
    preset_name: string;
    border_radius: number;
  };

  export type SchoolBrandingPublic = Omit<SchoolBranding, "id" | "school_id"> & {
    school_name: string;
    school_code: string;
  };

  export type LogoUploadResponse = {
    logo_url: string;
    branding: SchoolBranding;
  };

  export type AuthResponse = {
    access_token: string;
    token_type: string;
    expires_in?: number | null;
    refresh_expires_in?: number | null;
    user: User;
    school?: School | null;
  };

  export type FieldConfig = {
    name: string;
    label: string;
    type?: "text" | "number" | "date" | "checkbox" | "textarea" | "select";
    placeholder?: string;
    required?: boolean;
    emptyLabel?: string;
    valueType?: "string" | "number";
    options?: Array<{ label: string; value: string | number }>;
    optionsEndpoint?: string;
    optionLabelKey?: string;
    optionValueKey?: string;
  };

  export type AcademicClass = {
    id: number;
    academic_session_id?: number | null;
    name: string;
    code?: string | null;
    department_id?: number | null;
    sections?: string | null;
    is_active: boolean;
  };

  export type Section = {
    id: number;
    academic_session_id?: number | null;
    name: string;
    class_id: number;
    is_active: boolean;
  };

  export type Subject = {
    id: number;
    academic_session_id?: number | null;
    name: string;
    code?: string | null;
    department_id?: number | null;
    class_id?: number | null;
    is_active: boolean;
  };

  export type Department = {
    id: number;
    academic_session_id?: number | null;
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
    user_id?: number | null;
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
    academic_session_id?: number | null;
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
    section_name?: string | null;
    guardian?: ParentGuardian | null;
    status: string;
    is_active: boolean;
    user_id?: number | null;
    temporary_password?: string | null;
    parent_temporary_password?: string | null;
    parent_login_id?: string | null;
  };

  export type Teacher = {
    id: number;
    academic_session_id?: number | null;
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
    section_name?: string | null;
  };

  export type ClassTeacherAssignment = {
    id: number;
    teacher_id: number;
    class_id: number;
    section_id?: number | null;
    section_name?: string | null;
    academic_session_id?: number | null;
  };


  export type AttendanceRecord = {
    id: number;
    student_id: number;
    class_id: number;
    section_id?: number | null;
    section_name?: string | null;
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
    section_name?: string | null;
    academic_session_id?: number | null;
    class_name?: string | null;
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
    start_time?: string | null;
    end_time?: string | null;
    room?: string | null;
    timetable_note?: string | null;
    is_active: boolean;
    marks_entered_count: number;
    created_at: string;
    updated_at: string;
  };


  export type ExamTimetableItem = {
    exam_id: number;
    exam_name: string;
    exam_type?: string | null;
    result_status: string;
    class_id: number;
    section_id?: number | null;
    class_name?: string | null;
    section_name?: string | null;
    start_date?: string | null;
    end_date?: string | null;
    exam_subject_id: number;
    subject_id: number;
    subject_name?: string | null;
    teacher_id?: number | null;
    teacher_name?: string | null;
    max_marks: number;
    pass_marks: number;
    exam_date?: string | null;
    start_time?: string | null;
    end_time?: string | null;
    room?: string | null;
    timetable_note?: string | null;
    schedule_source: string;
    student_id?: number | null;
    student_name?: string | null;
    admission_no?: string | null;
    roll_number?: string | null;
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
  export type FeeMetaItem = {
    id: number;
    name: string;
    extra?: string | null;
  };

  export type FeeMeta = {
    categories: FeeMetaItem[];
    structures: FeeMetaItem[];
    classes: FeeMetaItem[];
    sections: FeeMetaItem[];
    students: FeeMetaItem[];
    academic_sessions: FeeMetaItem[];
    current_academic_session_id?: number | null;
  };

  export type FeeCategory = {
    id: number;
    name: string;
    code?: string | null;
    description?: string | null;
    is_active: boolean;
    created_at: string;
    updated_at: string;
  };

  export type FeeStructure = {
    id: number;
    name: string;
    category_id: number;
    category_name?: string | null;
    academic_session_id?: number | null;
    academic_session_name?: string | null;
    amount: number;
    due_date?: string | null;
    description?: string | null;
    is_active: boolean;
    created_at: string;
    updated_at: string;
  };

  export type FeeAssignment = {
    id: number;
    fee_structure_id: number;
    fee_structure_name?: string | null;
    academic_session_id?: number | null;
    academic_session_name?: string | null;
    class_id?: number | null;
    class_name?: string | null;
    section_id?: number | null;
    section_name?: string | null;
    student_id?: number | null;
    student_name?: string | null;
    assigned_amount?: number | null;
    due_date?: string | null;
    note?: string | null;
    is_active: boolean;
    generated_records_count: number;
    generated_at?: string | null;
    created_at: string;
    updated_at: string;
  };

  export type StudentFeeRecord = {
    id: number;
    student_id: number;
    student_name?: string | null;
    admission_no?: string | null;
    roll_number?: string | null;
    class_name?: string | null;
    section_name?: string | null;
    fee_structure_id?: number | null;
    fee_structure_name?: string | null;
    category_id?: number | null;
    category_name?: string | null;
    fee_type?: string | null;
    fee_assignment_id?: number | null;
    academic_session_id?: number | null;
    academic_session_name?: string | null;
    title: string;
    amount: number;
    discount_amount: number;
    fine_amount: number;
    paid_amount: number;
    balance_amount: number;
    due_date?: string | null;
    status: string;
    note?: string | null;
    created_at: string;
    updated_at: string;
  };

  export type FeePayment = {
    id: number;
    student_fee_record_id: number;
    student_id: number;
    student_name?: string | null;
    admission_no?: string | null;
    fee_title?: string | null;
    receipt_no: string;
    amount: number;
    payment_date: string;
    payment_mode: string;
    reference_no?: string | null;
    note?: string | null;
    collected_by_user_id?: number | null;
    collected_by_name?: string | null;
    created_at: string;
  };

  export type FeeReceipt = {
    payment: FeePayment;
    record: StudentFeeRecord;
    school_name?: string | null;
    school_code?: string | null;
  };

  export type FeeExpense = {
    id: number;
    title: string;
    category?: string | null;
    amount: number;
    expense_date: string;
    payment_mode: string;
    vendor_name?: string | null;
    reference_no?: string | null;
    note?: string | null;
    is_active: boolean;
    created_by_user_id?: number | null;
    created_by_name?: string | null;
    created_at: string;
    updated_at: string;
  };

  export type FeeDashboard = {
    total_records: number;
    pending_records: number;
    partial_records: number;
    paid_records: number;
    overdue_records: number;
    total_billable: number;
    total_paid: number;
    total_pending: number;
    today_collection: number;
    month_collection: number;
    month_expense: number;
    net_month_collection: number;
  };

  export type DailyCollectionReport = {
    report_date: string;
    total_collection: number;
    total_payments: number;
    payment_mode_summary: Record<string, number>;
    payments: FeePayment[];
  };

  export type FeePortalResponse = {
    role: string;
    summary: FeeDashboard;
    records: StudentFeeRecord[];
    payments: FeePayment[];
  };

  export type ProfileUser = User & {
    is_active?: boolean;
  };

  export type ProfileMiniStudent = {
    id: number;
    name: string;
    admission_no: string;
    roll_number?: string | null;
    email?: string | null;
    phone?: string | null;
    class_id?: number | null;
    class_name?: string | null;
    section_id?: number | null;
    section_name?: string | null;
    status?: string | null;
    class_teachers?: ProfileClassTeacher[];
    subject_teachers?: ProfileSubjectTeacher[];
  };

  export type ProfileSubjectTeacher = {
    id: number;
    teacher_id: number;
    teacher_name?: string | null;
    subject_id: number;
    subject_name?: string | null;
    class_id?: number | null;
    class_name?: string | null;
    section_id?: number | null;
    section_name?: string | null;
  };

  export type ProfileClassTeacher = {
    id: number;
    teacher_id: number;
    teacher_name?: string | null;
    class_id: number;
    class_name?: string | null;
    section_id?: number | null;
    section_name?: string | null;
    academic_session_id?: number | null;
    academic_session_name?: string | null;
  };

  export type ProfileStudent = {
    id: number;
    user_id?: number | null;
    admission_no: string;
    roll_number?: string | null;
    first_name: string;
    last_name?: string | null;
    full_name: string;
    email?: string | null;
    phone?: string | null;
    gender?: string | null;
    date_of_birth?: string | null;
    blood_group?: string | null;
    photo_url?: string | null;
    address?: string | null;
    admission_date?: string | null;
    class_id?: number | null;
    class_name?: string | null;
    section_id?: number | null;
    section_name?: string | null;
    status?: string | null;
    guardian?: ParentGuardian | null;
  };

  export type ProfileTeacher = {
    id: number;
    user_id?: number | null;
    employee_id: string;
    full_name: string;
    email?: string | null;
    phone?: string | null;
    gender?: string | null;
    department_id?: number | null;
    department_name?: string | null;
    qualification?: string | null;
    specialization?: string | null;
    joining_date?: string | null;
    photo_url?: string | null;
    address?: string | null;
    status?: string | null;
  };

  export type ProfileAssignedClass = {
    class_id: number;
    class_name?: string | null;
    section_id?: number | null;
    section_name?: string | null;
    subjects: ProfileSubjectTeacher[];
    is_class_teacher: boolean;
    class_teacher_assignment?: ProfileClassTeacher;
    students: ProfileMiniStudent[];
  };

  export type ProfileAdminClass = {
    id: number;
    name: string;
    code?: string | null;
    sections: { id: number; name: string }[];
    students: ProfileMiniStudent[];
    subjects: { id: number; name: string; code?: string | null }[];
    subject_teachers: ProfileSubjectTeacher[];
    class_teachers: ProfileClassTeacher[];
  };

  export type MyProfile = {
    user: ProfileUser;
    school?: School | null;
    editable_fields: string[];
    profile?: Record<string, unknown> | null;
    admin_overview?: {
      stats: {
        total_classes: number;
        total_students: number;
        total_teachers: number;
      };
      classes: ProfileAdminClass[];
      teachers: {
        id: number;
        name: string;
        employee_id: string;
        email?: string | null;
        phone?: string | null;
        department_id?: number | null;
        department_name?: string | null;
      }[];
    } | null;
    teacher_overview?: {
      teacher?: ProfileTeacher | null;
      assigned_classes: ProfileAssignedClass[];
      subject_assignments: ProfileSubjectTeacher[];
      class_teacher_assignments: ProfileClassTeacher[];
    } | null;
    student_overview?: {
      student: ProfileStudent;
      class_teachers: ProfileClassTeacher[];
      subject_teachers: ProfileSubjectTeacher[];
    } | null;
    parent_overview?: {
      guardians: ParentGuardian[];
      children: ProfileMiniStudent[];
    } | null;
  };

  export type CourseMetaItem = {
    id: number;
    name: string;
    extra?: string | null;
  };

  export type CourseMeta = {
    classes: CourseMetaItem[];
    sections: CourseMetaItem[];
    subjects: CourseMetaItem[];
    teachers: CourseMetaItem[];
    current_academic_session_id?: number | null;
  };

  export type LMSCourse = {
    id: number;
    title: string;
    description?: string | null;
    thumbnail_url?: string | null;
    school_id?: number | null;
    class_id?: number | null;
    section_id?: number | null;
    subject_id?: number | null;
    academic_session_id?: number | null;
    teacher_id: number;
    teacher_name?: string | null;
    class_name?: string | null;
    section_name?: string | null;
    subject_name?: string | null;
    academic_session_name?: string | null;
    status: string;
    is_active: boolean;
    lessons_count: number;
    enrolled_students_count: number;
    progress?: number | null;
    student_id?: number | null;
    student_name?: string | null;
    admission_no?: string | null;
    created_at: string;
    updated_at?: string | null;
  };

  export type LMSLesson = {
    id: number;
    title: string;
    description?: string | null;
    order: number;
    video_url?: string | null;
    pdf_url?: string | null;
    external_video_link?: string | null;
    course_id: number;
    language?: string | null;
    created_at: string;
  };

  export type LessonProgressItem = {
    lesson_id: number;
    title: string;
    order: number;
    completed: boolean;
    completed_at?: string | null;
    has_video: boolean;
    has_trackable_video?: boolean;
    watched_seconds?: number;
    video_duration_seconds?: number;
    required_watch_seconds?: number;
    watch_percentage?: number;
    required_watch_percentage?: number;
    requirement_progress_percentage?: number;
    can_mark_complete?: boolean;
  };

  export type CourseProgress = {
    course_id: number;
    overall_progress: number;
    total_lessons: number;
    completed_lessons: number;
    lessons: LessonProgressItem[];
  };


  export type LMSStudentLessonProgress = {
    lesson_id: number;
    title: string;
    order: number;
    completed: boolean;
    completed_at?: string | null;
    has_video: boolean;
    watched_seconds?: number;
    video_duration_seconds?: number;
    watch_percentage?: number;
    required_watch_percentage?: number;
    requirement_progress_percentage?: number;
  };

  export type LMSStudentProgress = {
    enrollment_id: number;
    student_user_id: number;
    student_id?: number | null;
    student_name: string;
    student_email?: string | null;
    admission_no?: string | null;
    roll_number?: string | null;
    progress: number;
    status: string;
    total_lessons: number;
    completed_lessons: number;
    pending_lessons: number;
    enrolled_at?: string | null;
    last_activity_at?: string | null;
    lessons: LMSStudentLessonProgress[];
  };

  export type LMSCourseProgressReport = {
    course: LMSCourse;
    total_students: number;
    average_progress: number;
    completed_students: number;
    in_progress_students: number;
    not_started_students: number;
    total_lessons: number;
    students: LMSStudentProgress[];
  };

  export type ChatSession = {
    id: string;
    title?: string | null;
    user_id?: number | null;
    created_at?: string | null;
    updated_at?: string | null;
  };

  export type ChatMessage = {
    id: number | string;
    role: "user" | "assistant" | "system" | "tool" | string;
    content?: string | null;
    created_at?: string | null;
    session_id?: string | null;
    user_id?: number | null;
    is_enhanced?: boolean;
  };
