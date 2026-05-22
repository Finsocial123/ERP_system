"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  CalendarCheck,
  CreditCard,
  GraduationCap,
  RefreshCw,
  Search,
  UserRound,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { AppSection } from "@/components/CrudManager";
import { Button, Card, Input } from "@/components/ui";
import { apiFetch } from "@/lib/api";

type DashboardCard = {
  key: string;
  label: string;
  value: number | string;
  helper?: string;
  tone?: "default" | "info" | "success" | "warning";
};

type ChartItem = {
  label: string;
  value: number;
};

type ChartBlock = {
  title: string;
  type: string;
  items: ChartItem[];
};

type ActivityItem = {
  kind: string;
  title: string;
  description?: string | null;
  created_at?: string | null;
};

type SearchResult = {
  kind: string;
  title: string;
  subtitle: string;
  href?: string | null;
};

type Overview = {
  school: { id: number; name: string; type: string; school_code: string } | null;
  user: { id: number; full_name: string; role: string; login_id?: string | null; must_change_password?: boolean };
  phase: string;
  role_dashboard: "admin" | "teacher" | "student" | "parent";
  title: string;
  description: string;
  cards: DashboardCard[];
  counts: Record<string, number | string>;
  current_academic_session?: {
    id: number;
    name: string;
    start_date?: string | null;
    end_date?: string | null;
    is_active: boolean;
  } | null;
  recent_activities: ActivityItem[];
  charts: ChartBlock[];
  next_steps: string[];
  quick_search_enabled: boolean;
};

const cardIcons: Record<string, LucideIcon> = {
  teachers: UserRound,
  students: Users,
  today_attendance: CalendarCheck,
  pending_fees: CreditCard,
  new_admissions: GraduationCap,
  current_session: GraduationCap,
  my_subjects: BookOpen,
  my_classes: GraduationCap,
  total_students: Users,
  pending_homework: Activity,
  homework: BookOpen,
  homework_created: BookOpen,
  submissions_to_check: Activity,
  attendance_percent: CalendarCheck,
  notices: Bell,
  children: Users,
  attendance_alerts: CalendarCheck,
  current_class: GraduationCap,
  timetable_slots: CalendarCheck,
};

const toneClass: Record<string, string> = {
  default: "bg-slate-100 text-slate-700",
  info: "bg-blue-50 text-blue-700",
  success: "bg-emerald-50 text-emerald-700",
  warning: "bg-amber-50 text-amber-700",
};

function formatDate(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

function formatValue(value: number | string) {
  if (typeof value === "number") return value.toLocaleString();
  return value || "-";
}

function SimpleBarChart({ chart }: { chart: ChartBlock }) {
  const maxValue = Math.max(1, ...chart.items.map((item) => item.value));

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="font-bold text-slate-900">{chart.title}</h3>
          <p className="text-xs text-slate-500">Basic Phase 3 chart</p>
        </div>
        <div className="rounded-2xl bg-slate-100 p-3 text-slate-700">
          <BarChart3 size={20} />
        </div>
      </div>

      <div className="space-y-3">
        {chart.items.map((item) => {
          const width = `${Math.max(4, Math.round((item.value / maxValue) * 100))}%`;
          return (
            <div key={`${chart.title}-${item.label}`}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="font-medium text-slate-600">{item.label}</span>
                <span className="font-semibold text-slate-900">{item.value}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div className="h-full rounded-full bg-slate-900" style={{ width }} />
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export default function RoleDashboard() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  const loadDashboard = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError("");

    try {
      const overview = await apiFetch<Overview>("/dashboard/overview");
      setData(overview);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  useEffect(() => {
    const query = search.trim();
    if (!query) {
      setSearchResults([]);
      return;
    }

    const timer = window.setTimeout(async () => {
      setSearching(true);
      try {
        const response = await apiFetch<{ results: SearchResult[] }>(`/dashboard/quick-search?q=${encodeURIComponent(query)}`);
        setSearchResults(response.results);
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 350);

    return () => window.clearTimeout(timer);
  }, [search]);

  const visibleTitle = data?.title || "Dashboard";
  const visibleDescription = data?.description || "Quick ERP analytics and activity summary.";

  const sessionText = useMemo(() => {
    if (!data?.current_academic_session) return "No active academic session selected";
    const session = data.current_academic_session;
    const dates = session.start_date || session.end_date ? `${formatDate(session.start_date)} - ${formatDate(session.end_date)}` : "Dates not set";
    return `${session.name} · ${dates}`;
  }, [data]);

  return (
    <AppSection title={visibleTitle} description={visibleDescription}>
      {error && <p className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {loading ? (
        <p className="text-slate-500">Loading dashboard...</p>
      ) : data ? (
        <>
          <Card className="mb-6 bg-slate-900 text-white">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-sm text-slate-300">{data.phase}</p>
                <h2 className="mt-2 text-2xl font-bold">{data.school?.name || "School ERP"}</h2>
                <div className="mt-3 grid gap-2 text-sm text-slate-300 sm:grid-cols-3">
                  <p>School code: <span className="font-semibold text-white">{data.school?.school_code || "-"}</span></p>
                  <p>User: <span className="font-semibold text-white">{data.user.full_name}</span></p>
                  <p>Role: <span className="font-semibold text-white">{data.user.role}</span></p>
                </div>
                <p className="mt-3 text-sm text-slate-300">Session: <span className="font-semibold text-white">{sessionText}</span></p>
              </div>

              <Button
                type="button"
                onClick={() => loadDashboard(true)}
                disabled={refreshing}
                className="w-full bg-white text-slate-900 hover:bg-slate-100 lg:w-auto"
              >
                <span className="inline-flex items-center justify-center gap-2">
                  <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
                  {refreshing ? "Refreshing..." : "Refresh Dashboard"}
                </span>
              </Button>
            </div>
          </Card>

          <Card className="mb-6">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h3 className="font-bold text-slate-900">Quick Search</h3>
                <p className="text-sm text-slate-500">Search students, teachers, classes, subjects or homework based on your role.</p>
              </div>
              <div className="relative w-full lg:max-w-md">
                <Search className="absolute left-3 top-2.5 text-slate-400" size={18} />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search name, ID, class, subject..."
                  className="pl-10"
                />
              </div>
            </div>

            {search.trim() && (
              <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                {searching ? (
                  <p className="text-sm text-slate-500">Searching...</p>
                ) : searchResults.length === 0 ? (
                  <p className="text-sm text-slate-500">No matching result found.</p>
                ) : (
                  <div className="grid gap-2 md:grid-cols-2">
                    {searchResults.map((result, index) => {
                      const body = (
                        <div className="rounded-xl border border-slate-200 bg-white p-3 transition hover:border-slate-300">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{result.kind}</p>
                          <p className="font-semibold text-slate-900">{result.title}</p>
                          <p className="text-sm text-slate-500">{result.subtitle}</p>
                        </div>
                      );

                      return result.href ? (
                        <Link key={`${result.kind}-${result.title}-${index}`} href={result.href}>
                          {body}
                        </Link>
                      ) : (
                        <div key={`${result.kind}-${result.title}-${index}`}>{body}</div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </Card>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
            {data.cards.map((card) => {
              const Icon = cardIcons[card.key] || Activity;
              const tone = toneClass[card.tone || "default"] || toneClass.default;
              return (
                <Card key={card.key}>
                  <div className="flex h-full flex-col justify-between gap-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm text-slate-500">{card.label}</p>
                        <p className="mt-2 text-3xl font-bold text-slate-900">{formatValue(card.value)}</p>
                      </div>
                      <div className={`rounded-2xl p-3 ${tone}`}>
                        <Icon size={22} />
                      </div>
                    </div>
                    {card.helper && <p className="text-xs text-slate-500">{card.helper}</p>}
                  </div>
                </Card>
              );
            })}
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-3">
            <div className="space-y-6 xl:col-span-2">
              <div className="grid gap-4 lg:grid-cols-2">
                {data.charts.map((chart) => (
                  <SimpleBarChart key={chart.title} chart={chart} />
                ))}
              </div>
            </div>

            <div className="space-y-6">
              <Card>
                <h3 className="font-bold text-slate-900">Recent Activities</h3>
                <div className="mt-4 space-y-3">
                  {data.recent_activities.length === 0 ? (
                    <p className="text-sm text-slate-500">No recent activity yet.</p>
                  ) : (
                    data.recent_activities.map((activity, index) => (
                      <div key={`${activity.kind}-${index}`} className="border-l-2 border-slate-200 pl-3">
                        <p className="text-sm font-semibold text-slate-900">{activity.title}</p>
                        {activity.description && <p className="text-sm text-slate-500">{activity.description}</p>}
                        <p className="text-xs text-slate-400">{formatDate(activity.created_at)}</p>
                      </div>
                    ))
                  )}
                </div>
              </Card>

              <Card>
                <h3 className="font-bold text-slate-900">Next Development Phases</h3>
                <div className="mt-3 flex flex-wrap gap-2">
                  {data.next_steps.map((step) => (
                    <span key={step} className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700">
                      {step}
                    </span>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        </>
      ) : null}
    </AppSection>
  );
}
