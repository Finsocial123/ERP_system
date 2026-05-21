from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.core.migrations import run_startup_migrations
from app.models import (  # noqa: F401
    AcademicSession,
    ClassTeacherAssignment,
    Department,
    ParentGuardian,
    School,
    SchoolClass,
    Section,
    Student,
    Subject,
    Teacher,
    TeacherSubject,
    User,
)
from app.routes import academic, auth, dashboard, people, schools

Base.metadata.create_all(bind=engine)
run_startup_migrations(engine)

app = FastAPI(title="School ERP Phase 3 API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "School ERP Phase 3 API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(schools.router)
app.include_router(academic.router)
app.include_router(people.router)
app.include_router(dashboard.router)
