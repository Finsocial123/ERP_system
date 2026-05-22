import type { TimetableEntry, TimetableGrid } from "@/types";

function formatTime(value?: string | null) {
  if (!value) return "";
  return value.slice(0, 5);
}

function slotText(entry?: TimetableEntry, mode?: string) {
  if (!entry) return <span className="text-slate-300">Free</span>;
  const title = entry.subject_name || (entry.period_name?.toLowerCase().includes("break") ? "Break" : "Activity");
  return (
    <div className="space-y-1">
      <p className="font-semibold text-slate-900">{title}</p>
      {mode === "teacher" && <p className="text-xs text-slate-600">{entry.class_name}{entry.section_name ? ` - ${entry.section_name}` : ""}</p>}
      {mode !== "teacher" && entry.teacher_name && <p className="text-xs text-slate-600">{entry.teacher_name}</p>}
      {entry.room && <p className="text-xs text-slate-500">Room: {entry.room}</p>}
      {entry.note && <p className="text-xs text-slate-400">{entry.note}</p>}
    </div>
  );
}

export default function TimetableGridView({ grid }: { grid: TimetableGrid }) {
  const entriesBySlot = new Map<string, TimetableEntry>();
  grid.entries.forEach((entry) => entriesBySlot.set(`${entry.day_id}-${entry.period_id}`, entry));

  if (!grid.days.length || !grid.periods.length) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
        Add active days and periods first to build the timetable grid.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr>
            <th className="sticky left-0 z-10 bg-slate-50 px-4 py-3 text-left font-semibold text-slate-700">Day</th>
            {grid.periods.map((period) => (
              <th key={period.id} className="min-w-44 px-4 py-3 text-left font-semibold text-slate-700">
                <div>{period.name}</div>
                <div className="text-xs font-normal text-slate-500">
                  P{period.period_number} {formatTime(period.start_time)}{period.end_time ? ` - ${formatTime(period.end_time)}` : ""}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {grid.days.map((day) => (
            <tr key={day.id}>
              <td className="sticky left-0 z-10 bg-white px-4 py-4 font-semibold text-slate-800">{day.display_name}</td>
              {grid.periods.map((period) => {
                const entry = entriesBySlot.get(`${day.id}-${period.id}`);
                return (
                  <td key={period.id} className={`align-top px-4 py-4 ${period.is_break ? "bg-amber-50" : ""}`}>
                    {slotText(entry, grid.mode)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
