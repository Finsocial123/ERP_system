import AppShell from "@/components/AppShell";
import ExamManager from "@/components/exams/ExamManager";

export default function TeacherExamsPage() {
  return (
    <AppShell>
      <ExamManager mode="teacher" />
    </AppShell>
  );
}
