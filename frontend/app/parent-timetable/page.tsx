import AppShell from "@/components/AppShell";
import TimetableViewer from "@/components/timetable/TimetableViewer";

export default function ParentTimetablePage() {
  return (
    <AppShell>
      <TimetableViewer role="parent" />
    </AppShell>
  );
}
