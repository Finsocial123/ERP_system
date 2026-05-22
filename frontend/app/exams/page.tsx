import AppShell from "@/components/AppShell";
import ExamManager from "@/components/exams/ExamManager";

export default function ExamsPage() {
  return (
    <AppShell>
      <ExamManager mode="admin" />
    </AppShell>
  );
}
