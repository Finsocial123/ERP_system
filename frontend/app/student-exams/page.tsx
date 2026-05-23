import AppShell from "@/components/AppShell";
import ReportCards from "@/components/exams/ReportCards";

export default function StudentExamsPage() {
  return (
    <AppShell>
      <ReportCards role="student" />
    </AppShell>
  );
}
