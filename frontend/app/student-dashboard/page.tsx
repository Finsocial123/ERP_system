import AppShell from "@/components/AppShell";
import RoleDashboard from "@/components/dashboard/RoleDashboard";
import NoticeWidget from "@/components/NoticeWidget";

export default function StudentDashboardPage() {
  return (
    <AppShell>
      <RoleDashboard />
      {/* <NoticeWidget /> */}
    </AppShell>
  );
}
