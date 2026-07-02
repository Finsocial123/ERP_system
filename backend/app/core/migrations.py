from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker

from app.core.utils import build_school_code, normalize_login_id, normalize_school_code
from app.models.school import School
from app.models.user import User


def _columns(engine, table_name: str) -> set[str]:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column(engine, table_name: str, column_name: str, ddl: str) -> None:
    if column_name in _columns(engine, table_name):
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))




def _table_exists(engine, table_name: str) -> bool:
    return table_name in inspect(engine).get_table_names()


def _execute_sql(engine, statement: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(statement))


def _drop_postgres_constraints(engine, table_name: str, constraint_names: list[str]) -> None:
    if engine.dialect.name != "postgresql" or not _table_exists(engine, table_name):
        return
    with engine.begin() as conn:
        for name in constraint_names:
            conn.execute(text(f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {name}"))


def _drop_postgres_indexes(engine, index_names: list[str]) -> None:
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        for name in index_names:
            conn.execute(text(f"DROP INDEX IF EXISTS {name}"))


def _create_postgres_unique_indexes(engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    indexes = [
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_departments_school_session_name_unique ON departments (school_id, academic_session_id, lower(name)) WHERE academic_session_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_school_classes_school_session_name_unique ON school_classes (school_id, academic_session_id, lower(name)) WHERE academic_session_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_sections_school_session_class_name_unique ON sections (school_id, academic_session_id, class_id, lower(name)) WHERE academic_session_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_subjects_school_session_class_name_unique ON subjects (school_id, academic_session_id, class_id, lower(name)) WHERE academic_session_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_students_school_session_admission_unique ON students (school_id, academic_session_id, admission_no) WHERE academic_session_id IS NOT NULL AND admission_no IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_teachers_school_session_employee_unique ON teachers (school_id, academic_session_id, employee_id) WHERE academic_session_id IS NOT NULL AND employee_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_teacher_subjects_session_scope_unique ON teacher_subjects (school_id, academic_session_id, teacher_id, subject_id, class_id, COALESCE(section_id, 0)) WHERE academic_session_id IS NOT NULL",
    ]
    with engine.begin() as conn:
        for statement in indexes:
            conn.execute(text(statement))


def _ensure_default_academic_sessions(engine) -> None:
    if not _table_exists(engine, "academic_sessions") or not _table_exists(engine, "schools"):
        return
    _execute_sql(
        engine,
        """
        INSERT INTO academic_sessions (school_id, name, start_date, end_date, is_active, created_at)
        SELECT schools.id, 'Current Session', NULL, NULL, TRUE, CURRENT_TIMESTAMP
        FROM schools
        WHERE NOT EXISTS (
            SELECT 1 FROM academic_sessions sessions
            WHERE sessions.school_id = schools.id
        )
        """,
    )
    _execute_sql(
        engine,
        """
        UPDATE academic_sessions
        SET is_active = FALSE
        WHERE is_active = TRUE
          AND id NOT IN (
              SELECT MAX(id)
              FROM academic_sessions
              WHERE is_active = TRUE
              GROUP BY school_id
          )
        """,
    )


def _backfill_session_column(engine, table_name: str) -> None:
    if not _table_exists(engine, table_name):
        return
    cols = _columns(engine, table_name)
    if "school_id" not in cols or "academic_session_id" not in cols:
        return
    _execute_sql(
        engine,
        f"""
        UPDATE {table_name}
        SET academic_session_id = (
            SELECT sessions.id
            FROM academic_sessions sessions
            WHERE sessions.school_id = {table_name}.school_id
            ORDER BY sessions.is_active DESC, sessions.id DESC
            LIMIT 1
        )
        WHERE academic_session_id IS NULL
        """,
    )


def _ensure_academic_session_scoping(engine) -> None:
    """Make core ERP master/data tables academic-session aware.

    Courses intentionally stay global: their academic_session_id is allowed to
    remain NULL and course access falls back to replicated class/section names.
    """
    scoped_tables = [
        "departments",
        "school_classes",
        "sections",
        "subjects",
        "students",
        "teachers",
        "teacher_subjects",
        "class_teacher_assignments",
        "homework_assignments",
        "exams",
        "timetable_entries",
        "fee_structures",
        "fee_assignments",
        "student_fee_records",
    ]

    for table_name in scoped_tables:
        _add_column(engine, table_name, "academic_session_id", "academic_session_id INTEGER")

    _ensure_default_academic_sessions(engine)

    for table_name in scoped_tables:
        _backfill_session_column(engine, table_name)

    # LMS courses are intentionally global across academic sessions.
    if _table_exists(engine, "courses") and "academic_session_id" in _columns(engine, "courses"):
        _execute_sql(engine, "UPDATE courses SET academic_session_id = NULL")

    _drop_postgres_constraints(engine, "departments", ["uq_department_school_name"])
    _drop_postgres_constraints(engine, "school_classes", ["uq_class_school_name"])
    _drop_postgres_constraints(engine, "sections", ["uq_section_school_class_name"])
    _drop_postgres_constraints(engine, "subjects", ["uq_subject_school_name", "uq_subject_school_session_name"])
    _drop_postgres_constraints(engine, "students", ["uq_student_school_admission_no"])
    _drop_postgres_constraints(engine, "teachers", ["uq_teacher_school_employee_id"])
    _drop_postgres_constraints(engine, "teacher_subjects", ["uq_teacher_subject_scope"])
    _drop_postgres_indexes(engine, ["ix_subjects_school_session_name_unique"])
    _create_postgres_unique_indexes(engine)



def _ensure_class_sections_dependency_fields(engine) -> None:
    """Move section dependency to SchoolClass.sections + section_name fields.

    The legacy sections table and section_id columns stay during this phase only
    so foreign keys/old rows do not break. All new feature logic should use the
    new text fields and validate against school_classes.sections.
    """
    if not _table_exists(engine, "school_classes"):
        return

    _add_column(engine, "school_classes", "sections", "sections TEXT")

    section_name_tables = [
        "students",
        "student_attendance",
        "teacher_subjects",
        "class_teacher_assignments",
        "homework_assignments",
        "exams",
        "timetable_entries",
        "fee_assignments",
        "courses",
        "meetings",
        "notice_class_audiences",
    ]
    existing_section_name_tables = [name for name in section_name_tables if _table_exists(engine, name)]
    for table_name in existing_section_name_tables:
        _add_column(engine, table_name, "section_name", "section_name VARCHAR(80)")

    index_specs = [
        ("students", "ix_students_school_session_class_section_name", ["school_id", "academic_session_id", "class_id", "section_name"]),
        ("student_attendance", "ix_attendance_school_session_class_section_name", ["school_id", "session_id", "class_id", "section_name"]),
        ("teacher_subjects", "ix_teacher_subjects_school_session_class_section_name", ["school_id", "academic_session_id", "class_id", "section_name"]),
        ("class_teacher_assignments", "ix_class_teachers_school_session_class_section_name", ["school_id", "academic_session_id", "class_id", "section_name"]),
        ("homework_assignments", "ix_homework_school_session_class_section_name", ["school_id", "academic_session_id", "class_id", "section_name"]),
        ("exams", "ix_exams_school_session_class_section_name", ["school_id", "academic_session_id", "class_id", "section_name"]),
        ("timetable_entries", "ix_timetable_school_session_class_section_name", ["school_id", "academic_session_id", "class_id", "section_name"]),
        ("fee_assignments", "ix_fee_assignments_school_session_class_section_name", ["school_id", "academic_session_id", "class_id", "section_name"]),
        ("courses", "ix_courses_school_session_class_section_name", ["school_id", "academic_session_id", "class_id", "section_name"]),
        ("meetings", "ix_meetings_school_session_class_section_name", ["school_id", "academic_session_id", "class_id", "section_name"]),
        ("notice_class_audiences", "ix_notice_audience_class_section_name", ["class_id", "section_name"]),
    ]
    for table_name, index_name, columns in index_specs:
        existing_columns = _columns(engine, table_name)
        if table_name in existing_section_name_tables and all(column in existing_columns for column in columns):
            _execute_sql(engine, f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({', '.join(columns)})")

    if not _table_exists(engine, "sections"):
        return

    if engine.dialect.name == "postgresql":
        _execute_sql(
            engine,
            """
            UPDATE school_classes AS c
            SET sections = source.section_names
            FROM (
                SELECT class_id, string_agg(name, ', ' ORDER BY lower(name)) AS section_names
                FROM sections
                WHERE is_active IS TRUE
                GROUP BY class_id
            ) AS source
            WHERE c.id = source.class_id
              AND (c.sections IS NULL OR btrim(c.sections) = '')
            """,
        )
        for table_name in existing_section_name_tables:
            _execute_sql(
                engine,
                f"""
                UPDATE {table_name} AS target
                SET section_name = s.name
                FROM sections AS s
                WHERE target.section_id = s.id
                  AND (target.section_name IS NULL OR btrim(target.section_name) = '')
                """,
            )
    else:
        _execute_sql(
            engine,
            """
            UPDATE school_classes
            SET sections = (
                SELECT group_concat(name, ', ')
                FROM sections
                WHERE sections.class_id = school_classes.id
                  AND sections.is_active = 1
            )
            WHERE (sections IS NULL OR trim(sections) = '')
              AND EXISTS (
                SELECT 1
                FROM sections
                WHERE sections.class_id = school_classes.id
                  AND sections.is_active = 1
              )
            """,
        )
        for table_name in existing_section_name_tables:
            _execute_sql(
                engine,
                f"""
                UPDATE {table_name}
                SET section_name = (
                    SELECT sections.name
                    FROM sections
                    WHERE sections.id = {table_name}.section_id
                )
                WHERE (section_name IS NULL OR trim(section_name) = '')
                  AND section_id IS NOT NULL
                """,
            )

def _ensure_video_watch_progress_table(engine) -> None:
    """Ensure lesson video watch progress persists on existing VPS databases."""
    if not _table_exists(engine, "users") or not _table_exists(engine, "lessons"):
        return

    if not _table_exists(engine, "video_watch_progress"):
        if engine.dialect.name == "postgresql":
            _execute_sql(
                engine,
                """
                CREATE TABLE IF NOT EXISTS video_watch_progress (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                    watched_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
                    video_duration_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
                    max_position_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
                    last_position_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
                    last_watch_ping_at TIMESTAMP WITH TIME ZONE NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_student_lesson_video_watch UNIQUE (student_id, lesson_id)
                )
                """,
            )
        else:
            _execute_sql(
                engine,
                """
                CREATE TABLE IF NOT EXISTS video_watch_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                    watched_seconds FLOAT NOT NULL DEFAULT 0,
                    video_duration_seconds FLOAT NOT NULL DEFAULT 0,
                    max_position_seconds FLOAT NOT NULL DEFAULT 0,
                    last_position_seconds FLOAT NOT NULL DEFAULT 0,
                    last_watch_ping_at TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_student_lesson_video_watch UNIQUE (student_id, lesson_id)
                )
                """,
            )

    _add_column(engine, "video_watch_progress", "watched_seconds", "watched_seconds FLOAT NOT NULL DEFAULT 0")
    _add_column(engine, "video_watch_progress", "video_duration_seconds", "video_duration_seconds FLOAT NOT NULL DEFAULT 0")
    _add_column(engine, "video_watch_progress", "max_position_seconds", "max_position_seconds FLOAT NOT NULL DEFAULT 0")
    _add_column(engine, "video_watch_progress", "last_position_seconds", "last_position_seconds FLOAT NOT NULL DEFAULT 0")
    _add_column(engine, "video_watch_progress", "last_watch_ping_at", "last_watch_ping_at TIMESTAMP")
    _add_column(engine, "video_watch_progress", "created_at", "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    _add_column(engine, "video_watch_progress", "updated_at", "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    if engine.dialect.name == "postgresql":
        _execute_sql(
            engine,
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_video_watch_progress_student_lesson_unique ON video_watch_progress (student_id, lesson_id)",
        )
        _execute_sql(
            engine,
            "CREATE INDEX IF NOT EXISTS ix_video_watch_progress_student_id ON video_watch_progress (student_id)",
        )
        _execute_sql(
            engine,
            "CREATE INDEX IF NOT EXISTS ix_video_watch_progress_lesson_id ON video_watch_progress (lesson_id)",
        )

def run_startup_migrations(engine) -> None:
    """Small dev migration layer for the tutorial project.

    This keeps existing SQLite/PostgreSQL dev databases usable after adding auth
    columns. For production, replace this with Alembic migrations.
    """
    _add_column(engine, "schools", "school_code", "school_code VARCHAR(40)")
    _add_column(engine, "users", "login_id", "login_id VARCHAR(255)")
    _add_column(engine, "users", "must_change_password", "must_change_password BOOLEAN DEFAULT FALSE")
    _add_column(engine, "users", "password_reset_token_hash", "password_reset_token_hash VARCHAR(255)")
    _add_column(engine, "users", "password_reset_expires_at", "password_reset_expires_at TIMESTAMP")
    _add_column(engine, "users", "last_login_at", "last_login_at TIMESTAMP")
    _add_column(engine, "users", "failed_login_attempts", "failed_login_attempts INTEGER DEFAULT 0")
    _add_column(engine, "users", "locked_until", "locked_until TIMESTAMP")
    _add_column(engine, "parent_guardians", "user_id", "user_id INTEGER")

    # LMS integration: make legacy courses ERP-aware without breaking old dev DBs.
    _add_column(engine, "courses", "school_id", "school_id INTEGER")
    _add_column(engine, "courses", "class_id", "class_id INTEGER")
    _add_column(engine, "courses", "section_id", "section_id INTEGER")
    _add_column(engine, "courses", "subject_id", "subject_id INTEGER")
    _add_column(engine, "courses", "academic_session_id", "academic_session_id INTEGER")
    _add_column(engine, "courses", "status", "status VARCHAR(30) DEFAULT 'PUBLISHED'")
    _add_column(engine, "courses", "is_active", "is_active BOOLEAN DEFAULT TRUE")
    _add_column(engine, "courses", "updated_at", "updated_at TIMESTAMP")

    _add_column(engine, "exam_subjects", "start_time", "start_time TIME")
    _add_column(engine, "exam_subjects", "end_time", "end_time TIME")
    _add_column(engine, "exam_subjects", "room", "room VARCHAR(120)")
    _add_column(engine, "exam_subjects", "timetable_note", "timetable_note TEXT")

    _ensure_academic_session_scoping(engine)
    _ensure_class_sections_dependency_fields(engine)
    _ensure_video_watch_progress_table(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        used_codes: set[str] = set()
        schools = db.query(School).all()
        for school in schools:
            if school.school_code:
                used_codes.add(school.school_code)

        for school in schools:
            if not school.school_code:
                counter = 1
                code = normalize_school_code(build_school_code(school.slug or school.name, counter))
                while code in used_codes:
                    counter += 1
                    code = normalize_school_code(build_school_code(school.slug or school.name, counter))
                school.school_code = code
                used_codes.add(code)

        users = db.query(User).all()
        for user in users:
            if not user.login_id:
                user.login_id = normalize_login_id(user.email or f"USER{user.id}")
            if user.must_change_password is None:
                user.must_change_password = False
            if user.failed_login_attempts is None:
                user.failed_login_attempts = 0

        db.commit()
    finally:
        db.close()

def run_phase4_migrations(engine) -> None:
    """Ensure student_attendance table exists with all required columns."""
    # The table is created by Base.metadata.create_all, but we guard
    # any future column additions here for existing deployments.
    _add_column(engine, "student_attendance", "note", "note TEXT")
