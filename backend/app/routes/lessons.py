from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
import httpx
from sqlalchemy.orm import Session
from typing import Optional, Annotated
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from io import BytesIO


from app.core.database import get_db, get_async_db
from app.models.lesson import Lesson, LessonChunk
from app.models.course import Course
from app.models.user import User
from app.schemas.lesson import LessonOut, SummaryRequest
from app.utils.dependencies import get_current_user, require_role
from app.utils.cloudinary import upload_file, delete_file
from app.services.embedder import chunk_and_embed_lesson
from app.services.extractor import extract_text_from_pdf
from app.services.transcriber import transcribe_video
from app.services.frame_analyzer import analyze_video_frames
from app.services.embedder import embed_visual_frames
from app.services.tools.summarizer import summarize_lesson

from io import BytesIO


router = APIRouter(
    prefix="/lessons",
    tags=["Lessons"]
)

ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB


def course_owner_or_admin(course: Course, user: User):
    if user.role != "admin" and course.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Not your course")



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
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    course_owner_or_admin(course, current_user)  

    video_url = None
    video_public_id = None
    transcript = None
    segments = []

    if video:
        video_bytes = await video.read()

        if video.content_type not in ALLOWED_VIDEO_TYPES:
            raise HTTPException(status_code=400, detail="Invalid video format")
        if len(video_bytes) > MAX_VIDEO_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Max 500MB")

        upload_result = upload_file(
            BytesIO(video_bytes),
            folder="lms/videos",
            resource_type="video"
        )
        video_url = upload_result["url"]
        video_public_id = upload_result["public_id"]

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

    if pdf:
        pdf_bytes = await pdf.read()
        upload_result = upload_file(
            BytesIO(pdf_bytes),
            folder="lms/pdfs",
            resource_type="raw"
        )
        pdf_url = upload_result["url"]
        pdf_public_id = upload_result["public_id"]
        pdf_text = extract_text_from_pdf(pdf_bytes)

    lesson = Lesson(
        title=title,
        description=description,
        language=language,
        order=order,
        external_video_link=external_video_link,
        video_url=video_url,
        video_public_id=video_public_id,
        transcript=transcript,
        pdf_url=pdf_url,
        pdf_public_id=pdf_public_id,
        notes=pdf_text,
        course_id=course_id
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

    # Process visual frames from video
    if video_bytes:
        try:
            print(f"Analyzing visual content from video for lesson {lesson.id}...")
            frames = await analyze_video_frames(
                video_bytes=video_bytes,
                interval_seconds=15,  # Extract frame every 15 seconds
                max_frames=30  # Max 30 frames per video
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
            # Don't fail the entire upload if visual analysis fails

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


# Get all lessons for a course
@router.get("/course/{course_id}")
def get_course_lessons(
    course_id: int,
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    lessons = db.query(Lesson).filter(
        Lesson.course_id == course_id
    ).order_by(Lesson.order).all()

    return lessons


# Get single lesson
@router.get("/{lesson_id}")
def get_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()

    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    return lesson


# Update lesson
@router.put("/{lesson_id}")
def update_lesson(
    lesson_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    order: Optional[int] = Form(None),
    external_video_link: Optional[str] = Form(None),
    video: Optional[UploadFile] = File(None),
    pdf: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()

    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    course = db.query(Course).filter(Course.id == lesson.course_id).first()
    course_owner_or_admin(course, current_user)

    if title:
        lesson.title = title

    if description is not None:
        lesson.description = description

    if order is not None:
        lesson.order = order

    if external_video_link is not None:
        lesson.external_video_link = external_video_link

    if video:
        # delete old video
        if lesson.video_public_id:
            delete_file(lesson.video_public_id, resource_type="video")

        result = upload_file(
            video.file,
            folder="lms/videos",
            resource_type="video"
        )
        lesson.video_url = result["url"]
        lesson.video_public_id = result["public_id"]

    if pdf:
        # delete old pdf
        if lesson.pdf_public_id:
            delete_file(lesson.pdf_public_id, resource_type="raw")

        result = upload_file(
            pdf.file,
            folder="lms/pdfs",
            resource_type="raw"
        )
        lesson.pdf_url = result["url"]
        lesson.pdf_public_id = result["public_id"]

    db.commit()
    db.refresh(lesson)

    return {"message": "Lesson updated successfully"}


# Delete lesson
@router.delete("/{lesson_id}")
def delete_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["teacher", "admin"]))
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()

    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    course = db.query(Course).filter(Course.id == lesson.course_id).first()
    course_owner_or_admin(course, current_user)

    # clean up cloudinary files
    if lesson.video_public_id:
        delete_file(lesson.video_public_id, resource_type="video")

    if lesson.pdf_public_id:
        delete_file(lesson.pdf_public_id, resource_type="raw")

    db.delete(lesson)
    db.commit()

    return {"message": "Lesson deleted successfully"}


@router.post('/{lesson_id}/course/{course_id}/{source}/summary')
async def generate_lesson_summary(
    course_id: int, 
    lesson_id: int,
    source: str,
    db: Annotated[AsyncSession, Depends(get_async_db)]
):
    
    result = await db.execute(
        select(Course)
        .where(Course.id == course_id))
    
    course = result.scalars().first()

    if not course:
        raise HTTPException(status_code=404, description="Course not found")
    
    result = await db.execute(
        select(Lesson)
        .where(Lesson.id == lesson_id, Lesson.course_id == course_id)
    )

    lesson = result.scalars().first()

    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    result = (await db.execute(
        select(LessonChunk)
        .where(LessonChunk.lesson_id == lesson_id)
        .limit(1)
    ))

    chunks_exits = result.scalars().first()
    if not chunks_exits:
        raise HTTPException(
            status_code=422,
            detail="No content for this lesson. Upload a PDF or Video first"
        )

    try:
        summary = await summarize_lesson(
            lesson_id=lesson_id,
            lesson_order=lesson.order,
            lesson_title=lesson.title,
            source=source,
            db=db
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return summary

