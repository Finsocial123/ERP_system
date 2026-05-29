import AppShell from "@/components/AppShell";
import CourseManager from "@/components/courses/CourseManager";

export default function TeacherCoursesPage() {
  return (
    <AppShell>
      <CourseManager mode="teacher" />
    </AppShell>
  );
}
