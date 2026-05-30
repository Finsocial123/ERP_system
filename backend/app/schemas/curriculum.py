from pydantic import BaseModel, Field

# to save token maybe needed to do this for other schema too
class CurriculumRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=200)
    target_audience: str = Field(..., min_length=3, max_length=200)
    duration_weeks: int = Field(default=4, ge=1, le=16)
    num_lessons: int = Field(default=10, ge=3, le=30)
    language: str = Field(default="en", max_length=10)

class LessonPlan(BaseModel):
    title: str
    description: str | None = None
    order: int

class CurriculumPlan(BaseModel):
    course_title: str
    course_description: str
    target_audience: str
    duration_weeks: int
    lessons: list[LessonPlan]

class CurriculumApproveRequest(BaseModel):
    plan: CurriculumPlan
    course_id: int | None = None
    class_id: int
    section_id: int | None = None
    subject_id: int | None = None