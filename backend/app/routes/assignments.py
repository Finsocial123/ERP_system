from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.dependencies.auth import current_school_id
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Annotated
from datetime import datetime, timezone
from sqlalchemy import select
import json
from app.services.tools.quiz_generator import generate_quiz
from app.core.database import get_async_db
from app.models.assignment import Assignment
from app.models.lesson import Lesson
from app.models.lesson import LessonChunk
from app.models.submission import Submission
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User, UserRole
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate, QuizRequest
from app.schemas.submission import GradeSubmission
from app.utils.dependencies import require_role
from app.utils.cloudinary import upload_file
from app.core.async_query import async_query
router = APIRouter(prefix='/assignments', tags=['Assignments'])

def course_owner_or_admin(course: Course | None, user: User):
    admin_roles = {
        UserRole.SUPER_ADMIN.value,
        UserRole.SCHOOL_OWNER.value,
        UserRole.SCHOOL_ADMIN.value,
        'ADMIN',
    }
    if not course:
        raise HTTPException(status_code=404, detail='Course not found')
    if user.role not in admin_roles and course.teacher_id != user.id:
        raise HTTPException(status_code=403, detail='Not your course')

@router.post('/{course_id}')
async def create_assignment(course_id: int, data: AssignmentCreate, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(require_role(['TEACHER', 'ADMIN']))):
    course = await async_query(db, Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail='Course not found')
    course_owner_or_admin(course, current_user)
    assignment = Assignment(title=data.title, description=data.description, due_date=data.due_date, course_id=course_id)
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return {'message': 'Assignment created successfully', 'assignment_id': assignment.id}

@router.get('/course/{course_id}')
async def get_course_assignments(course_id: int, db: AsyncSession=Depends(get_async_db)):
    course = await async_query(db, Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail='Course not found')
    assignments = await async_query(db, Assignment).filter(Assignment.course_id == course_id).all()
    return assignments

@router.put('/{assignment_id}')
async def update_assignment(assignment_id: int, data: AssignmentUpdate, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(require_role(['TEACHER', 'ADMIN']))):
    assignment = await async_query(db, Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail='Assignment not found')
    course = await async_query(db, Course).filter(Course.id == assignment.course_id).first()
    course_owner_or_admin(course, current_user)
    if data.title is not None:
        assignment.title = data.title
    if data.description is not None:
        assignment.description = data.description
    if data.due_date is not None:
        assignment.due_date = data.due_date
    await db.commit()
    await db.refresh(assignment)
    return {'message': 'Assignment updated successfully'}

@router.delete('/{assignment_id}')
async def delete_assignment(assignment_id: int, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(require_role(['TEACHER', 'ADMIN']))):
    assignment = await async_query(db, Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail='Assignment not found')
    course = await async_query(db, Course).filter(Course.id == assignment.course_id).first()
    course_owner_or_admin(course, current_user)
    await db.delete(assignment)
    await db.commit()
    return {'message': 'Assignment deleted successfully'}

@router.post('/{assignment_id}/submit')
async def submit_assignment(assignment_id: int, file: Optional[UploadFile]=File(None), db: AsyncSession=Depends(get_async_db), current_user: User=Depends(require_role(['STUDENT']))):
    assignment = await async_query(db, Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail='Assignment not found')
    if assignment.due_date:
        due_date = assignment.due_date
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)
        if due_date < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail='Assignment deadline has passed')
    enrollment = await async_query(db, Enrollment).filter(Enrollment.student_id == current_user.id, Enrollment.course_id == assignment.course_id).first()
    if not enrollment:
        raise HTTPException(status_code=403, detail='You are not enrolled in this course')
    existing = await async_query(db, Submission).filter(Submission.student_id == current_user.id, Submission.assignment_id == assignment_id).first()
    if existing:
        raise HTTPException(status_code=400, detail='You have already submitted this assignment')
    file_url = None
    file_public_id = None
    if file:
        result = upload_file(file.file, folder='lms/submissions', resource_type='raw')
        file_url = result['url']
        file_public_id = result['public_id']
    submission = Submission(student_id=current_user.id, assignment_id=assignment_id, file_url=file_url, file_public_id=file_public_id)
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return {'message': 'Assignment submitted successfully'}

@router.get('/{assignment_id}/submissions')
async def get_submissions(assignment_id: int, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(require_role(['TEACHER', 'ADMIN']))):
    assignment = await async_query(db, Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail='Assignment not found')
    course = await async_query(db, Course).filter(Course.id == assignment.course_id).first()
    course_owner_or_admin(course, current_user)
    submissions = await async_query(db, Submission).filter(Submission.assignment_id == assignment_id).all()
    result = []
    for sub in submissions:
        student = await async_query(db, User).filter(User.id == sub.student_id).first()
        result.append({'id': sub.id, 'student_id': sub.student_id, 'student_name': student.full_name if student else None, 'file_url': sub.file_url, 'grade': sub.grade, 'feedback': sub.feedback, 'submitted_at': sub.submitted_at})
    return result

@router.put('/submissions/{submission_id}/grade')
async def grade_submission(submission_id: int, data: GradeSubmission, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(require_role(['TEACHER', 'ADMIN']))):
    if data.grade < 0 or data.grade > 100:
        raise HTTPException(status_code=400, detail='Grade must be between 0 and 100')
    submission = await async_query(db, Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail='Submission not found')
    assignment = await async_query(db, Assignment).filter(Assignment.id == submission.assignment_id).first()
    course = await async_query(db, Course).filter(Course.id == assignment.course_id).first()
    course_owner_or_admin(course, current_user)
    submission.grade = data.grade
    submission.feedback = data.feedback
    await db.commit()
    return {'message': 'Submission graded successfully'}

@router.get('/{assignment_id}/my-submission')
async def get_my_submission(assignment_id: int, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(require_role(['STUDENT']))):
    submission = await async_query(db, Submission).filter(Submission.student_id == current_user.id, Submission.assignment_id == assignment_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail='No submission found')
    return submission

@router.post('/api/course/{course_id}/lessons/{lesson_id}/quiz')
async def generate_lesson_quiz(course_id: int, lesson_id: int, request: QuizRequest, db: Annotated[AsyncSession, Depends(get_async_db)], school_id: int = Depends(current_school_id)):
    result = await db.execute(select(Course).where(course_id == Course.id))
    course = result.scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail='Course not found')
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id, Lesson.course_id == course_id))
    lesson = result.scalars().first()
    if not lesson:
        raise HTTPException(status_code=404, detail='Lesson not found in this course')
    chunk_count = (await db.execute(select(LessonChunk).where(LessonChunk.lesson_id == lesson_id).limit(1))).scalars().first()
    if not chunk_count:
        raise HTTPException(status_code=422, detail='No content found for this lesson. Upload a PDF or video first.')
    try:
        quiz = await generate_quiz(lesson_id=lesson_id, num_questions=request.num_questions, difficulty=request.difficulty, db=db, include_answers=True, school_id=school_id)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail='Failed to parse quiz response')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return quiz
