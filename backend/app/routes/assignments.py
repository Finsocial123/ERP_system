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
@router.post("/{course_id}")
def create_assignment(
    course_id: int,
    data: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    course_owner_or_admin(course, current_user)

    assignment = Assignment(
        title=data.title,
        description=data.description,
        due_date=data.due_date,
        course_id=course_id
    )

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return {
        "message": "Assignment created successfully",
        "assignment_id": assignment.id
    }


# Get all assignments for a course
@router.get("/course/{course_id}")
def get_course_assignments(
    course_id: int,
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    assignments = db.query(Assignment).filter(
        Assignment.course_id == course_id
    ).all()

    return assignments


# Update assignment
@router.put("/{assignment_id}")
def update_assignment(
    assignment_id: int,
    data: AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    course = db.query(Course).filter(
        Course.id == assignment.course_id
    ).first()

    course_owner_or_admin(course, current_user)

    if data.title is not None:
        assignment.title = data.title

    if data.description is not None:
        assignment.description = data.description

    if data.due_date is not None:
        assignment.due_date = data.due_date

    db.commit()
    db.refresh(assignment)

    return {"message": "Assignment updated successfully"}


# Delete assignment
@router.delete("/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    course = db.query(Course).filter(
        Course.id == assignment.course_id
    ).first()

    course_owner_or_admin(course, current_user)

    db.delete(assignment)
    db.commit()

    return {"message": "Assignment deleted successfully"}


# Student submits assignment
@router.post("/{assignment_id}/submit")
def submit_assignment(
    assignment_id: int,
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Check assignment deadline
    if assignment.due_date:
        due_date = assignment.due_date

        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)

        if due_date < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400,
                detail="Assignment deadline has passed"
            )

    # Check student is enrolled in the course
    enrollment = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Enrollment.course_id == assignment.course_id
    ).first()

    if not enrollment:
        raise HTTPException(
            status_code=403,
            detail="You are not enrolled in this course"
        )

    # Check if already submitted
    existing = db.query(Submission).filter(
        Submission.student_id == current_user.id,
        Submission.assignment_id == assignment_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="You have already submitted this assignment"
        )

    file_url = None
    file_public_id = None

    if file:
        result = upload_file(
            file.file,
            folder="lms/submissions",
            resource_type="raw"
        )
        file_url = result["url"]
        file_public_id = result["public_id"]

    submission = Submission(
        student_id=current_user.id,
        assignment_id=assignment_id,
        file_url=file_url,
        file_public_id=file_public_id
    )

    db.add(submission)
    db.commit()
    db.refresh(submission)

    return {"message": "Assignment submitted successfully"}

# Teacher/admin views all submissions for an assignment
@router.get("/{assignment_id}/submissions")
def get_submissions(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    course = db.query(Course).filter(
        Course.id == assignment.course_id
    ).first()

    course_owner_or_admin(course, current_user)

    submissions = db.query(Submission).filter(
        Submission.assignment_id == assignment_id
    ).all()

    result = []
    for sub in submissions:
        student = db.query(User).filter(User.id == sub.student_id).first()
        result.append({
            "id": sub.id,
            "student_id": sub.student_id,
            "student_name": student.name if student else None,
            "file_url": sub.file_url,
            "grade": sub.grade,
            "feedback": sub.feedback,
            "submitted_at": sub.submitted_at
        })

    return result


# Teacher/admin grades a submission
@router.put("/submissions/{submission_id}/grade")
def grade_submission(
    submission_id: int,
    data: GradeSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    if data.grade < 0 or data.grade > 100:
        raise HTTPException(
            status_code=400,
            detail="Grade must be between 0 and 100"
        )

    submission = db.query(Submission).filter(
        Submission.id == submission_id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    assignment = db.query(Assignment).filter(
        Assignment.id == submission.assignment_id
    ).first()

    course = db.query(Course).filter(
        Course.id == assignment.course_id
    ).first()

    course_owner_or_admin(course, current_user)

    submission.grade = data.grade
    submission.feedback = data.feedback

    db.commit()

    return {"message": "Submission graded successfully"}


# Student views their own submission for an assignment
@router.get("/{assignment_id}/my-submission")
def get_my_submission(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    submission = db.query(Submission).filter(
        Submission.student_id == current_user.id,
        Submission.assignment_id == assignment_id
    ).first()

    if not submission:
        raise HTTPException(
            status_code=404,
            detail="No submission found"
        )

    return submission



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
