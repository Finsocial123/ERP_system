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

    _add_column(engine, "exam_subjects", "start_time", "start_time TIME")
    _add_column(engine, "exam_subjects", "end_time", "end_time TIME")
    _add_column(engine, "exam_subjects", "room", "room VARCHAR(120)")
    _add_column(engine, "exam_subjects", "timetable_note", "timetable_note TEXT")

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
