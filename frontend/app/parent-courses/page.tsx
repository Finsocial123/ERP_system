import AppShell from "@/components/AppShell";
import CoursePortal from "@/components/courses/CoursePortal";

export default function ParentCoursesPage() {
  return (
    <AppShell>
      <CoursePortal mode="parent" />
    </AppShell>
  );
}
