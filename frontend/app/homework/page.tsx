import AppShell from "@/components/AppShell";
import HomeworkManager from "@/components/homework/HomeworkManager";

export default function HomeworkPage() {
  return (
    <AppShell>
      <HomeworkManager mode="admin" />
    </AppShell>
  );
}
