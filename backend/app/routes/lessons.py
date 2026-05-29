from __future__ import annotations

from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import current_school_id, require_roles
from app.models.lesson import Lesson
from app.models.user import User
from app.services.lms_access import ALL_LMS_ROLES, MANAGER_ROLES, ensure_can_manage_course, ensure_can_view_course, get_course_or_404
from app.utils.cloudinary import delete_file, upload_file

from app.services.embedder import chunk_and_embed_lesson
from app.services.extractor import extract_text_from_pdf
from app.services.transcriber import transcribe_video
from app.services.frame_analyzer import analyze_video_frames
from app.services.embedder import embed_visual_frames
from app.services.tools.summarizer import summarize_lesson



router = APIRouter(prefix="/lessons", tags=["LMS Lessons"])

ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB


def _lesson_payload(lesson: Lesson) -> dict:
    return {
        "id": lesson.id,
        "title": lesson.title,
        "description": lesson.description,
        "order": lesson.order,
        "video_url": lesson.video_url,
        "pdf_url": lesson.pdf_url,
        "external_video_link": lesson.external_video_link,
        "course_id": lesson.course_id,
        "language": lesson.language,
        "created_at": lesson.created_at,
    }


def _get_lesson_or_404(db: Session, lesson_id: int) -> Lesson:
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
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
    db: Session = Depends(get_db),
):
    course = get_course_or_404(db, school_id, course_id)
    ensure_can_manage_course(db, school_id, current_user, course)

    video_url = None
    video_public_id = None
    transcript = None
    segments = []


    if video and video.filename:
        video_bytes = await video.read()

        if video.content_type not in ALLOWED_VIDEO_TYPES:
            raise HTTPException(status_code=400, detail="Invalid video format")
        
        if len(video_bytes) > MAX_VIDEO_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Max 500MB")
        
        result = upload_file(BytesIO(video_bytes), folder="lms/videos", resource_type="video")
        video_url = result["url"]
        video_public_id = result["public_id"]

        try:
            result = await transcribe_video(video_bytes)
            transcript = result["text"]
            segments = result["segments"]
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Transcription failed: {str(e)}")
        if not transcript:
            raise HTTPException(status_code=422, detail="Could not transcribe video")
        

    pdf_url = None
    pdf_public_id = None
    pdf_text = None

    if pdf and pdf.filename:
        pdf_bytes = await pdf.read()
        result = upload_file(BytesIO(pdf_bytes), folder="lms/pdfs", resource_type="raw")
        pdf_url = result["url"]
        pdf_public_id = result["public_id"]
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
    await db.commit()
    await db.refresh(lesson)

    transcript_chunks = 0   
    pdf_chunks = 0
    visual_chunks = 0

    if transcript:
        transcript_chunks = await chunk_and_embed_lesson(
            lesson_id=lesson.id,
            text=transcript,
            source="transcript",
            db=db,
            segments=segments
        )

    if video_bytes:
        try:
            print(f"Analyzing visual content from video for lesson {lesson.id}...")
            frames = await analyze_video_frames(
                video_bytes=video_bytes,
                interval_seconds=15,
                max_frames=30
            )
            if frames:
                visual_chunks = await embed_visual_frames(
                    lesson_id=lesson.id,
                    frames=frames,
                    db=db
                )
                print(f"Created {visual_chunks} visual chunks")
        except Exception as e:
            print(f"Visual analysis failed (non-critical): {e}")

    if pdf_text:
        pdf_chunks = await chunk_and_embed_lesson(
            lesson_id=lesson.id,
            text=pdf_text,
            source="notes",
            db=db
            # no segments for PDF
        )

    return {
        "lesson_id": lesson.id,
        "video_url": video_url,
        "pdf_url": pdf_url,
        "transcript_preview": transcript[:200] if transcript else None,
        "pdf_preview": pdf_text[:200] if pdf_text else None,
        "transcript_chunks": transcript_chunks,
        "pdf_chunks": pdf_chunks,
        "visual_chunks": visual_chunks,
        "message": "Lesson created successfully",
    }


@router.get("/course/{course_id}")
def get_course_lessons(
    course_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ALL_LMS_ROLES)),
    db: Session = Depends(get_db),
):
    course = get_course_or_404(db, school_id, course_id)
    ensure_can_view_course(db, school_id, current_user, course)
    lessons = db.query(Lesson).filter(Lesson.course_id == course_id).order_by(Lesson.order.asc(), Lesson.id.asc()).all()
    return [_lesson_payload(lesson) for lesson in lessons]


@router.get("/{lesson_id}")
def get_lesson(
    lesson_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*ALL_LMS_ROLES)),
    db: Session = Depends(get_db),
):
    lesson = _get_lesson_or_404(db, lesson_id)
    course = get_course_or_404(db, school_id, lesson.course_id)
    ensure_can_view_course(db, school_id, current_user, course)
    return _lesson_payload(lesson)


@router.put("/{lesson_id}")
def update_lesson(
    lesson_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    order: Optional[int] = Form(None),
    external_video_link: Optional[str] = Form(None),
    video: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    lesson = _get_lesson_or_404(db, lesson_id)
    course = get_course_or_404(db, school_id, lesson.course_id)
    ensure_can_manage_course(db, school_id, current_user, course)

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
            raise HTTPException(status_code=400, detail="Invalid video format")
        if lesson.video_public_id:
            delete_file(lesson.video_public_id, resource_type="video")
        result = upload_file(video.file, folder="lms/videos", resource_type="video")
        lesson.video_url = result["url"]
        lesson.video_public_id = result["public_id"]

    if pdf and pdf.filename:
        if lesson.pdf_public_id:
            delete_file(lesson.pdf_public_id, resource_type="raw")
        result = upload_file(pdf.file, folder="lms/pdfs", resource_type="raw")
        lesson.pdf_url = result["url"]
        lesson.pdf_public_id = result["public_id"]

    db.commit()
    db.refresh(lesson)
    return {"message": "Lesson updated successfully", "lesson": _lesson_payload(lesson)}


@router.delete("/{lesson_id}")
def delete_lesson(
    lesson_id: int,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
):
    lesson = _get_lesson_or_404(db, lesson_id)
    course = get_course_or_404(db, school_id, lesson.course_id)
    ensure_can_manage_course(db, school_id, current_user, course)

    if lesson.video_public_id:
        delete_file(lesson.video_public_id, resource_type="video")
    if lesson.pdf_public_id:
        delete_file(lesson.pdf_public_id, resource_type="raw")

    db.delete(lesson)
    db.commit()
    return {"message": "Lesson deleted successfully"}
