import json 
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.client import client
from app.core.config import MODEL
from app.models.course import Course
from app.models.lesson import Lesson
from app.schemas.curriculum import CurriculumPlan, CurriculumRequest
from app.instructions import CURRICULUM_PROMPT



async def generate_curriculum(request: CurriculumRequest) -> CurriculumPlan:
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": CURRICULUM_PROMPT
            },
            {
                "role": "user",
                "content": f"""
                    Generate a complete course curriculum for the following:

                    Topic: {request.topic}
                    Target Audience: {request.target_audience}
                    Duration: {request.duration_weeks} weeks
                    Number of Lessons: {request.num_lessons}
                    Language: {request.language}

                    Return this exact JSON structure:
                    {{
                        "course_title": "complete course title",
                        "course_description": "2-3 sentences course description",
                        "target_audience": "who this course is for",
                        "duration_weeks": {request.duration_weeks},]
                        "lessons": [
                            {{
                                "title": "lesson title",
                                "desciption":  "what this lesson covers in 1-2 sentences. THIS FIELD IS REQUIRED.",
                                "order": 1
                            }}
                        ]
                    }}
                """
            }
        ],
        stream=False
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    data = json.loads(raw)
    return CurriculumPlan(**data)


async def save_curriculum(
    plan: CurriculumPlan,
    course_id: int | None,
    current_user,
    db: AsyncSession
) -> Course:
    if course_id:
        course = (await db.execute(
            select(Course).where(Course.id == course_id)
        )).scalars().first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
    else:
        course = Course(
            title= plan.course_title,
            description=plan.course_description,
            teacher_id=current_user.id,
        )
        db.add(course)
        await db.flush()

    for lesson_plan in plan.lessons:
        lesson = Lesson(
            title=lesson_plan.title,
            description=lesson_plan.description,
            order=lesson_plan.order,
            course_id=course.id
        )
        db.add(lesson)

    await db.commit()
    await db.refresh(course)
    return course