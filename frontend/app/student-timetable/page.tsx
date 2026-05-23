import AppShell from "@/components/AppShell";
import TimetableViewer from "@/components/timetable/TimetableViewer";

export default function StudentTimetablePage() {
  return (
    <AppShell>
      <TimetableViewer role="student" />
    </AppShell>
  );
}
