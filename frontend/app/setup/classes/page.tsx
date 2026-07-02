import AppShell from "@/components/AppShell";
import CrudManager from "@/components/CrudManager";

export default function ClassesPage() {
  return (
    <AppShell>
      <CrudManager
        title="Classes"
        description="Create classes/courses and manage their section names from the class itself."
        endpoint="/classes"
        fields={[
          { name: "name", label: "Class Name", placeholder: "Class 10 / BCA 1st Year", required: true },
          { name: "code", label: "Code", placeholder: "10 / BCA1" },
          // { name: "department_id", label: "Department", type: "select", optionsEndpoint: "/departments", optionValueKey: "id", optionLabelKey: "name", valueType: "number", emptyLabel: "No department / school class" },
          { name: "sections", label: "Sections", type: "textarea", placeholder: "A, B, C or one section per line" },
        ]}
      />
    </AppShell>
  );
}
