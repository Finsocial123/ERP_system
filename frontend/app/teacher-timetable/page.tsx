import AppShell from "@/components/AppShell";
import TimetableViewer from "@/components/timetable/TimetableViewer";

export default function TeacherTimetablePage() {
  return (
    <AppShell>
      <TimetableViewer role="teacher" />
    </AppShell>
  );
}
