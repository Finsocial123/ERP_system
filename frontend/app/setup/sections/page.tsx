import AppShell from "@/components/AppShell";
import CrudManager from "@/components/CrudManager";

export default function SectionsPage() {
  return (
    <AppShell>
      <CrudManager
        title="Sections"
        description="Create sections inside classes. Use the class ID shown in the Classes page."
        endpoint="/sections"
        fields={[
          { name: "name", label: "Section Name", placeholder: "A", required: true },
          { name: "class_id", label: "Class ID", type: "number", required: true },
        ]}
      />
    </AppShell>
  );
}
