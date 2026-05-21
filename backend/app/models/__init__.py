from app.models.academic import AcademicSession, Department, SchoolClass, Section, Subject
from app.models.people import ClassTeacherAssignment, ParentGuardian, Student, Teacher, TeacherSubject
from app.models.school import School
from app.models.user import User

__all__ = [
    "School",
    "User",
    "AcademicSession",
    "Department",
    "SchoolClass",
    "Section",
    "Subject",
    "ParentGuardian",
    "Student",
    "Teacher",
    "TeacherSubject",
    "ClassTeacherAssignment",
]
