"""
lessons.py — fixed get_lesson_summary to pass school_id to generate_and_save_summary.

Bug fixed:
  get_lesson_summary did not accept or pass school_id, so the summary was
  generated and stored in Redis under school_id=0 for every school.
  Two schools' summaries for the same lesson_id would collide.

Fix: added school_id = Depends(current_school_id) and passes it through.
"""

from __future__ import annotations
from io import BytesIO
from typing import Optional, Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db, get_async_db, get_session_factory
from app.dependencies.auth import current_school_id, require_roles
from app.models.lesson import Lesson, LessonChunk
from app.models.user import User
from app.models.course import Course
from app.schemas.assignment import QuizRequest
from app.services.lms_access import (
    ALL_LMS_ROLES, MANAGER_ROLES,
    ensure_can_manage_course, ensure_can_view_course,
    get_course_or_404, async_get_course_or_404, async_ensure_can_manage_course,
)
from app.utils.cloudinary import delete_file, upload_file
from app.services.embedder import chunk_and_embed_lesson
from app.services.extractor import extract_text_from_pdf
from app.services.transcriber import transcribe_video
from app.services.frame_analyzer import analyze_video_frames
from app.services.embedder import embed_visual_frames
from app.services.tools.quiz_generator import generate_quiz
from app.services.tools.summarizer import generate_and_save_summary
from app.services.ai_cache import ai_cache, compute_content_hash
from app.core.async_query import async_query
from app.services.notification_service import notify_student_scope

import asyncio
from functools import partial
import cloudinary
import cloudinary.uploader
from sqlalchemy import delete, select
import json

router = APIRouter(prefix='/lessons', tags=['LMS Lessons'])
ALLOWED_VIDEO_TYPES = {'video/mp4', 'video/webm', 'video/quicktime'}
MAX_VIDEO_SIZE = settings.LMS_MAX_VIDEO_UPLOAD_MB * 1024 * 1024
AI_VIDEO_PROCESSING_MAX_SIZE = settings.LMS_AI_PROCESS_VIDEO_MAX_MB * 1024 * 1024


def _format_mb(size_bytes: int | None) -> str:
    if size_bytes is None:
        return 'unknown size'
    return f'{size_bytes / (1024 * 1024):.1f}MB'


def _upload_size(upload: UploadFile) -> int | None:
    """Return UploadFile size without loading the whole video into memory."""
    try:
        current = upload.file.tell()
        upload.file.seek(0, 2)
        size = upload.file.tell()
        upload.file.seek(current)
        return int(size)
    except Exception:
        return None


async def _upload_to_cloudinary(upload: UploadFile, *, folder: str, resource_type: str) -> dict:
    await upload.seek(0)
    return await asyncio.to_thread(partial(upload_file, upload.file, folder=folder, resource_type=resource_type))


async def _clear_lesson_chunks(db: AsyncSession, lesson_id: int, sources: set[str]) -> None:
    await db.execute(delete(LessonChunk).where(LessonChunk.lesson_id == lesson_id, LessonChunk.source.in_(sources)))
    await db.commit()


async def _process_lesson_content_background(
    lesson_id: int,
    school_id: int,
    video_bytes: bytes | None = None,
    pdf_text: str | None = None,
    language: str = 'en',
) -> None:
    """Build AI transcript/PDF/visual chunks after the upload request returns.

    Long videos are intentionally not passed here by default because transcription
    and frame analysis can take many minutes and can exhaust small VPS memory.
    The video itself is still saved and playable for students.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
        lesson = result.scalars().first()
        if not lesson:
            return

        chunks_created = 0

        if video_bytes:
            try:
                result = await transcribe_video(video_bytes, language=language or 'en')
                transcript = result.get('text') or ''
                segments = result.get('segments') or []
                if transcript:
                    chunks_created += await chunk_and_embed_lesson(
                        lesson_id=lesson.id, text=transcript, source='transcript', db=db, segments=segments
                    )
            except Exception as exc:
                print(f'Video transcription failed for lesson {lesson_id} (non-critical): {exc}')

            try:
                frames = await analyze_video_frames(video_bytes=video_bytes, interval_seconds=15, max_frames=30)
                if frames:
                    chunks_created += await embed_visual_frames(lesson_id=lesson.id, frames=frames, db=db)
            except Exception as exc:
                print(f'Visual analysis failed for lesson {lesson_id} (non-critical): {exc}')

        if pdf_text:
            try:
                chunks_created += await chunk_and_embed_lesson(
                    lesson_id=lesson.id, text=pdf_text, source='notes', db=db
                )
            except Exception as exc:
                print(f'PDF embedding failed for lesson {lesson_id} (non-critical): {exc}')

        if chunks_created:
            try:
                await generate_and_save_summary(
                    lesson.id,
                    lesson.order,
                    lesson.title,
                    AsyncSessionLocal,
                    school_id,
                )
            except Exception as exc:
                print(f'Lesson summary generation failed for lesson {lesson_id} (non-critical): {exc}')



def _lesson_payload(lesson: Lesson) -> dict:
    return {
        'id': lesson.id, 'title': lesson.title, 'description': lesson.description,
        'order': lesson.order, 'video_url': lesson.video_url, 'pdf_url': lesson.pdf_url,
        'external_video_link': lesson.external_video_link, 'course_id': lesson.course_id,
        'language': lesson.language, 'created_at': lesson.created_at,
    }


async def _get_lesson_or_404(db: AsyncSession, lesson_id: int) -> Lesson:
    lesson = await async_query(db, Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail='Lesson not found')
    return lesson


async def _async_get_lesson_or_404(db: AsyncSession, lesson_id: int) -> Lesson:
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalars().first()
    if not lesson:
        raise HTTPException(status_code=404, detail='Lesson not found')
    return lesson


@router.post("/{course_id}")
async def create_lesson(
    course_id: int,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    language: str = Form("en"),
    order: Optional[int] = Form(0),
    external_video_link: Optional[str] = Form(None),
    video: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    course = await async_get_course_or_404(db, school_id, course_id)
    await async_ensure_can_manage_course(db, school_id, current_user, course)

    video_url = None
    video_bytes_for_ai: bytes | None = None
    video_public_id = None
    video_ai_queued = False
    video_ai_skipped_reason = None

    if video and video.filename:
        if video.content_type not in ALLOWED_VIDEO_TYPES:
            raise HTTPException(status_code=400, detail='Invalid video format. Upload MP4, WebM, or MOV only.')

        video_size = _upload_size(video)
        if video_size is not None and video_size > MAX_VIDEO_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f'Video is too large ({_format_mb(video_size)}). Max allowed is {settings.LMS_MAX_VIDEO_UPLOAD_MB}MB.',
            )

        try:
            result = await _upload_to_cloudinary(video, folder='lms/videos', resource_type='video')
        except Exception as exc:
            raise HTTPException(status_code=502, detail='Video upload failed. Please try again or compress the video.') from exc

        video_url = result['url']
        video_public_id = result['public_id']

        # AI indexing is useful for chat/search, but doing it inside the upload
        # request causes timeouts for 1-hour lessons. Keep upload reliable first.
        if video_size is None or video_size <= AI_VIDEO_PROCESSING_MAX_SIZE:
            await video.seek(0)
            video_bytes_for_ai = await video.read()
            video_ai_queued = bool(video_bytes_for_ai)
        else:
            video_ai_skipped_reason = (
                f'Video saved, but AI transcript/frame indexing was skipped because the file is {_format_mb(video_size)}. '
                f'Current AI indexing limit is {settings.LMS_AI_PROCESS_VIDEO_MAX_MB}MB.'
            )

    pdf_url = None
    pdf_public_id = None
    pdf_text = None
    if pdf and pdf.filename:
        pdf_bytes = await pdf.read()
        try:
            result = await asyncio.to_thread(partial(upload_file, BytesIO(pdf_bytes), folder='lms/pdfs', resource_type='raw'))
        except Exception as exc:
            raise HTTPException(status_code=502, detail='PDF upload failed. Please try again.') from exc
        pdf_url = result['url']
        pdf_public_id = result['public_id']
        pdf_text = extract_text_from_pdf(pdf_bytes)

    lesson = Lesson(
        title=title.strip(),
        description=description.strip() if description else None,
        language=language,
        order=order or 0,
        external_video_link=external_video_link.strip() if external_video_link else None,
        video_url=video_url,
        video_public_id=video_public_id,
        pdf_url=pdf_url,
        pdf_public_id=pdf_public_id,
        course_id=course_id,
    )
    db.add(lesson)
    await db.flush()
    if course.status == 'PUBLISHED':
        await notify_student_scope(
            db,
            school_id=school_id,
            class_id=course.class_id,
            section_id=course.section_id,
            academic_session_id=None,
            title='New lesson added',
            message=f"{lesson.title} was added to {course.title}.",
            category='COURSE',
            priority='NORMAL',
            created_by=current_user.id,
            student_link='/student-courses',
            parent_link='/parent-courses',
        )
    await db.commit()
    await db.refresh(lesson)

    if video_bytes_for_ai or pdf_text:
        background_tasks.add_task(
            _process_lesson_content_background,
            lesson.id,
            school_id,
            video_bytes_for_ai,
            pdf_text,
            language or 'en',
        )

    return {
        "lesson_id": lesson.id,
        "video_url": video_url,
        "pdf_url": pdf_url,
        "video_ai_queued": video_ai_queued,
        "video_ai_skipped_reason": video_ai_skipped_reason,
        "message": "Lesson created successfully",
    }


@router.get("/course/{course_id}")
async def get_course_lessons(
    course_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ALL_LMS_ROLES)),
    db: Session = Depends(get_async_db),
):
    course = await get_course_or_404(db, school_id, course_id)
    await ensure_can_view_course(db, school_id, current_user, course)
    lessons = await (
    async_query(db, Lesson)
    .filter(Lesson.course_id == course_id)
    .order_by(Lesson.order.asc(), Lesson.id.asc())
    .all()
    )
    return [_lesson_payload(lesson) for lesson in lessons]


@router.get('/{lesson_id}')
async def get_lesson(
    lesson_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ALL_LMS_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    lesson = await _get_lesson_or_404(db, lesson_id)
    course = await get_course_or_404(db, school_id, lesson.course_id)
    await ensure_can_view_course(db, school_id, current_user, course)
    return _lesson_payload(lesson)


@router.put('/{lesson_id}')
async def update_lesson(
    lesson_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    order: Optional[int] = Form(None),
    external_video_link: Optional[str] = Form(None),
    video: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    lesson = await _get_lesson_or_404(db, lesson_id)
    course = await get_course_or_404(db, school_id, lesson.course_id)
    await ensure_can_manage_course(db, school_id, current_user, course)

    content_changed = False
    video_bytes_for_ai: bytes | None = None
    pdf_text: str | None = None
    video_ai_skipped_reason = None

    if title is not None:
        lesson.title = title.strip()
    if description is not None:
        lesson.description = description.strip() if description else None
    if order is not None:
        lesson.order = order
    if external_video_link is not None:
        lesson.external_video_link = external_video_link.strip() if external_video_link else None

    if video and video.filename:
        if video.content_type not in ALLOWED_VIDEO_TYPES:
            raise HTTPException(status_code=400, detail='Invalid video format. Upload MP4, WebM, or MOV only.')

        video_size = _upload_size(video)
        if video_size is not None and video_size > MAX_VIDEO_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f'Video is too large ({_format_mb(video_size)}). Max allowed is {settings.LMS_MAX_VIDEO_UPLOAD_MB}MB.',
            )

        if lesson.video_public_id:
            await asyncio.to_thread(partial(delete_file, lesson.video_public_id, resource_type='video'))
        try:
            result = await _upload_to_cloudinary(video, folder='lms/videos', resource_type='video')
        except Exception as exc:
            raise HTTPException(status_code=502, detail='Video upload failed. Please try again or compress the video.') from exc
        lesson.video_url = result['url']
        lesson.video_public_id = result['public_id']
        lesson.summary = None
        content_changed = True

        await _clear_lesson_chunks(db, lesson_id, {'transcript', 'visual'})
        if video_size is None or video_size <= AI_VIDEO_PROCESSING_MAX_SIZE:
            await video.seek(0)
            video_bytes_for_ai = await video.read()
        else:
            video_ai_skipped_reason = (
                f'Video saved, but AI transcript/frame indexing was skipped because the file is {_format_mb(video_size)}. '
                f'Current AI indexing limit is {settings.LMS_AI_PROCESS_VIDEO_MAX_MB}MB.'
            )

    if pdf and pdf.filename:
        if lesson.pdf_public_id:
            await asyncio.to_thread(partial(delete_file, lesson.pdf_public_id, resource_type='raw'))
        pdf_bytes = await pdf.read()
        try:
            result = await asyncio.to_thread(partial(upload_file, BytesIO(pdf_bytes), folder='lms/pdfs', resource_type='raw'))
        except Exception as exc:
            raise HTTPException(status_code=502, detail='PDF upload failed. Please try again.') from exc
        lesson.pdf_url = result['url']
        lesson.pdf_public_id = result['public_id']
        lesson.summary = None
        pdf_text = extract_text_from_pdf(pdf_bytes)
        await _clear_lesson_chunks(db, lesson_id, {'notes'})
        content_changed = True

    if course.status == 'PUBLISHED':
        await notify_student_scope(
            db,
            school_id=school_id,
            class_id=course.class_id,
            section_id=course.section_id,
            academic_session_id=None,
            title='Lesson updated',
            message=f"{lesson.title} in {course.title} was updated.",
            category='COURSE',
            priority='NORMAL',
            created_by=current_user.id,
            student_link='/student-courses',
            parent_link='/parent-courses',
        )
    await db.commit()
    await db.refresh(lesson)

    if content_changed:
        await ai_cache.invalidate_lesson(school_id, lesson_id)
        lesson.summary = None
        await db.commit()

    if video_bytes_for_ai or pdf_text:
        background_tasks.add_task(
            _process_lesson_content_background,
            lesson.id,
            school_id,
            video_bytes_for_ai,
            pdf_text,
            lesson.language or 'en',
        )

    return {
        'message': 'Lesson updated successfully',
        'lesson': _lesson_payload(lesson),
        'video_ai_queued': bool(video_bytes_for_ai),
        'video_ai_skipped_reason': video_ai_skipped_reason,
    }


@router.delete('/{lesson_id}')
async def delete_lesson(
    lesson_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: AsyncSession = Depends(get_async_db),
):
    lesson = await _get_lesson_or_404(db, lesson_id)
    course = await get_course_or_404(db, school_id, lesson.course_id)
    await ensure_can_manage_course(db, school_id, current_user, course)

    if lesson.video_public_id:
        delete_file(lesson.video_public_id, resource_type='video')
    if lesson.pdf_public_id:
        delete_file(lesson.pdf_public_id, resource_type='raw')

    await db.delete(lesson)
    await db.commit()
    await ai_cache.invalidate_lesson(school_id, lesson_id)

    return {'message': 'Lesson deleted successfully'}


@router.get("/{lesson_id}/summary")
async def get_lesson_summary(
    lesson_id: int,
    school_id: int = Depends(current_school_id),   # FIX: was missing — caused school_id=0 in cache key
    db: Annotated[AsyncSession, Depends(get_async_db)] = None,
    session_factory: Annotated[async_sessionmaker, Depends(get_session_factory)] = None,
):
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalars().first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    # Layer 1: DB field (fast path — no LLM or Redis needed)
    if lesson.summary:
        return json.loads(lesson.summary)

    # Layer 2: Generate + store in Redis + store in DB
    summary = await generate_and_save_summary(
        lesson_id=lesson.id,
        lesson_order=lesson.order,
        lesson_title=lesson.title,
        session_factory=session_factory,
        school_id=school_id,            # FIX: now correctly passed
    )

    if summary is None:
        raise HTTPException(status_code=422, detail="No content available to summarize")

    return summary


@router.post("/api/course/{course_id}/lessons/{lesson_id}/quiz")
async def generate_lesson_quiz(
    course_id: int,
    lesson_id: int,
    request: QuizRequest,
    school_id: int = Depends(current_school_id),
    db: Annotated[AsyncSession, Depends(get_async_db)] = None,
):
    result = await db.execute(select(Course).where(course_id == Course.id))
    course = result.scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail='Course not found')

    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id, Lesson.course_id == course_id))
    lesson = result.scalars().first()
    if not lesson:
        raise HTTPException(status_code=404, detail='Lesson not found in this course')

    chunk_count = (await db.execute(
        select(LessonChunk).where(LessonChunk.lesson_id == lesson_id).limit(1)
    )).scalars().first()
    if not chunk_count:
        raise HTTPException(status_code=422, detail='No content found for this lesson. Upload a PDF or video first.')

    try:
        quiz = await generate_quiz(
            lesson_id=lesson_id,
            num_questions=request.num_questions,
            difficulty=request.difficulty,
            db=db,
            include_answers=True,
            school_id=school_id,
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail='Failed to parse quiz response')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return quiz
