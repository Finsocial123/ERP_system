import AppShell from "@/components/AppShell";
import CrudManager from "@/components/CrudManager";

export default function SubjectsPage() {
  return (
    <AppShell>
      <CrudManager
        title="Subjects"
        description="Create subjects and optionally connect them with department or class."
        endpoint="/subjects"
        fields={[
          { name: "name", label: "Subject Name", placeholder: "Mathematics", required: true },
          { name: "code", label: "Code", placeholder: "MATH" },
          { name: "department_id", label: "Department ID", type: "number", placeholder: "Optional" },
          { name: "class_id", label: "Class ID", type: "number", placeholder: "Optional" },
        ]}
      />
    </AppShell>
  );
}
