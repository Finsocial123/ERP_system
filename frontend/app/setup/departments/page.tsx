import AppShell from "@/components/AppShell";
import CrudManager from "@/components/CrudManager";

export default function DepartmentsPage() {
  return (
    <AppShell>
      <CrudManager
        title="Departments"
        description="Create departments such as Science, Commerce, Arts, Computer Science."
        endpoint="/departments"
        fields={[
          { name: "name", label: "Department Name", placeholder: "Science", required: true },
          { name: "code", label: "Code", placeholder: "SCI" },
          { name: "description", label: "Description", type: "textarea" },
        ]}
      />
    </AppShell>
  );
}
