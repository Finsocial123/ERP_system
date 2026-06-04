from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import current_school_id, get_current_user, require_roles
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User, UserRole
from app.services.lms_access import ensure_enrollment_for_user_student, get_course_or_404, student_for_user

router = APIRouter(prefix="/enrollments", tags=["LMS Enrollments"])


