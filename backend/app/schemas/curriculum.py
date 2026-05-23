from pydantic import BaseModel

class CurriculumRequest(BaseModel):
    topic: str
    target_audience: str
    duration_weeks: int = 4
    num_lessons: int = 10
    language: str = "en"

class LessonPlan(BaseModel):
    title: str
    description: str
    order: int

class CurriculumPlan(BaseModel):
    course_title: str
    course_description: str
    target_audience: str
    duration_weeks: int
    lesson: list[LessonPlan]

class CurriculumApproveRequest(BaseModel):
    plan: CurriculumPlan
    course_id: int | None = None

