from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Annotated
from datetime import datetime, timezone
from sqlalchemy import select
import json
from app.services.tools.quiz_generator import generate_quiz

from app.core.database import get_db, get_async_db
from app.models.assignment import Assignment
from app.models.lesson import Lesson
from app.models.lesson import LessonChunk
from app.models.submission import Submission
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate, QuizRequest
from app.schemas.submission import GradeSubmission
from app.utils.dependencies import require_role
from app.utils.cloudinary import upload_file

router = APIRouter(
    prefix="/assignments",
    tags=["Assignments"]
)


def course_owner_or_admin(course: Course, user: User):
    if user.role != "admin" and course.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Not your course")


# Create assignment
# Get all assignments for a course
# Update assignment
# Delete assignment
# Student submits assignment
# Teacher/admin views all submissions for an assignment
# Teacher/admin grades a submission
# Student views their own submission for an assignment
@router.post("/api/course/{course_id}/lessons/{lesson_id}/quiz")
async def generate_lesson_quiz(
    course_id: int,
    lesson_id: int,
    request: QuizRequest,
    db: Annotated[AsyncSession, Depends(get_async_db)]
):

    result = await db.execute(select(Course).where(course_id == Course.id))
    course = result.scalars().first()

    if not course:
        raise HTTPException(status_code=404, description="Course not found")

    result = (await db.execute(
        select(Lesson)
        .where(
            Lesson.id == lesson_id,
            Lesson.course_id == course_id
        )
    ))
    lesson = result.scalars().first()

    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found in this course")
    
    chunk_count = (await db.execute(
        select(LessonChunk)
        .where(LessonChunk.lesson_id == lesson_id)
        .limit(1)
    )).scalars().first()
    if not chunk_count:
        raise HTTPException(
            status_code=422,
            detail="No content found for this lesson. Upload a PDF or video first."
        )

    try:
        quiz = await generate_quiz(
            lesson_id=lesson_id,
            num_questions=request.num_questions,
            difficulty=request.difficulty,
            db=db,
            include_answers=True
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse quiz response")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return quiz
