import AppShell from "@/components/AppShell";
import CrudManager from "@/components/CrudManager";

export default function AcademicSessionsPage() {
  return (
    <AppShell>
      <CrudManager
        title="Academic Sessions"
        description="Create and manage academic years like 2026-2027. Only one can be active."
        endpoint="/academic-sessions"
        fields={[
          { name: "name", label: "Session Name", placeholder: "2026-2027", required: true },
          { name: "start_date", label: "Start Date", type: "date" },
          { name: "end_date", label: "End Date", type: "date" },
          { name: "is_active", label: "Active", type: "checkbox" },
        ]}
      />
    </AppShell>
  );
}
