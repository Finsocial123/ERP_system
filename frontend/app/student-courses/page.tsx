import AppShell from "@/components/AppShell";
import CoursePortal from "@/components/courses/CoursePortal";

export default function StudentCoursesPage() {
  return (
    <AppShell>
      <CoursePortal mode="student" />
    </AppShell>
  );
}
