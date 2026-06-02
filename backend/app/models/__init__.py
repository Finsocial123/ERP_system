from app.models.academic import AcademicSession, Department, SchoolClass, Section, Subject
from app.models.people import ClassTeacherAssignment, ParentGuardian, Student, Teacher, TeacherSubject
from app.models.homework import HomeworkAssignment, HomeworkSubmission
from app.models.timetable import TimetableDay, TimetableEntry, TimetablePeriod
from app.models.exam import Exam, ExamSubject, ExamMark
from app.models.fee import FeeAssignment, FeeCategory, FeeExpense, FeePayment, FeeStructure, StudentFeeRecord
from app.models.school import School
from app.models.branding import SchoolBranding
from app.models.user import User
from app.models.verification import PendingSchoolRegistration
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.enrollment import Enrollment
from app.models.progress import LessonProgress
from app.models.video_watch_progress import VideoWatchProgress
from app.models.assignment import Assignment
from app.models.submission import Submission
from app.models.communication import (
    Announcement,
    Circular,
    Complaint,
    InAppNotification,
    InAppNotificationRead,
    SchoolEvent,
    SupportTicket,
)

__all__ = [
    "School",
    "SchoolBranding",
    "User",
    "PendingSchoolRegistration",
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
    "HomeworkAssignment",
    "HomeworkSubmission",
    "TimetableDay",
    "TimetableEntry",
    "TimetablePeriod",
    "ExamMark",
    "ExamSubject",
    "Exam",
    "FeeCategory",
    "FeeStructure",
    "FeeAssignment",
    "StudentFeeRecord",
    "FeePayment",
    "FeeExpense",
    "Announcement",
    "Circular",
    "Complaint",
    "InAppNotification",
    "InAppNotificationRead",
    "SchoolEvent",
    "SupportTicket",
    "Course",
    "Lesson",
    "Enrollment",
    "LessonProgress",
    "VideoWatchProgress",
    "Assignment",
    "Submission",
]
