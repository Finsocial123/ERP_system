import AppShell from "@/components/AppShell";
import CourseManager from "@/components/courses/CourseManager";

export default function CoursesPage() {
  return (
    <AppShell>
      <CourseManager mode="admin" />
    </AppShell>
  );
}
