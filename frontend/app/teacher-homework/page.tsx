import AppShell from "@/components/AppShell";
import HomeworkManager from "@/components/homework/HomeworkManager";

export default function TeacherHomeworkPage() {
  return (
    <AppShell>
      <HomeworkManager mode="teacher" />
    </AppShell>
  );
}
