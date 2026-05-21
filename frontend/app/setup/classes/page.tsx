import AppShell from "@/components/AppShell";
import CrudManager from "@/components/CrudManager";

export default function ClassesPage() {
  return (
    <AppShell>
      <CrudManager
        title="Classes"
        description="Create classes or courses. Department ID is optional for college mode."
        endpoint="/classes"
        fields={[
          { name: "name", label: "Class Name", placeholder: "Class 10 / BCA 1st Year", required: true },
          { name: "code", label: "Code", placeholder: "10 / BCA1" },
          { name: "department_id", label: "Department ID", type: "number", placeholder: "Optional" },
        ]}
      />
    </AppShell>
  );
}
