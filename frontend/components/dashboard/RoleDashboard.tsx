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
  ShieldCheck,
  UserRound,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { AppSection } from "@/components/CrudManager";
import { Button, Card, Input } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import NoticeWidget from "../NoticeWidget";

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
  exams: GraduationCap,
  published_results: GraduationCap,
  exam_subjects: BookOpen,
  marks_entered: Activity,
};

const toneClass: Record<string, string> = {
  default: "bg-slate-100 text-slate-700",
  info: "bg-blue-50 text-blue-700",
  success: "bg-emerald-50 text-emerald-700",
  warning: "bg-amber-50 text-amber-700",
};

const toneAccent: Record<string, string> = {
  default: "border-slate-200",
  info: "border-blue-100",
  success: "border-emerald-100",
  warning: "border-amber-100",
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

function formatRole(value: string) {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function SimpleBarChart({ chart }: { chart: ChartBlock }) {
  const maxValue = Math.max(1, ...chart.items.map((item) => item.value));

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold text-slate-900">{chart.title}</h3>
          <p className="text-xs text-slate-500">Live overview</p>
        </div>
        <div className="rounded-2xl bg-slate-100 p-3 text-slate-700">
          <BarChart3 size={20} />
        </div>
      </div>

      <div className="space-y-3">
        {chart.items.length === 0 ? (
          <p className="text-sm text-slate-500">No chart data available.</p>
        ) : (
          chart.items.map((item) => {
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
          })
        )}
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
    const dates =
      session.start_date || session.end_date
        ? `${formatDate(session.start_date)} - ${formatDate(session.end_date)}`
        : "Dates not set";
    return `${session.name} · ${dates}`;
  }, [data]);

  return (
    <AppSection title={visibleTitle} description={visibleDescription}>
      {error && (
        <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {loading ? (
        <Card>
          <p className="text-sm text-slate-500">Loading dashboard...</p>
        </Card>
      ) : data ? (
        <>
          {/* ── Hero banner ── */}
          <Card className="mb-6 overflow-hidden p-0">
            <div className="border-b border-slate-100 bg-linear-to-r from-slate-50 to-white px-5 py-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0">
                  <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 shadow-sm">
                    <ShieldCheck size={14} /> Secure ERP Portal
                  </div>
                  <h2 className="truncate text-2xl font-bold text-slate-900">
                    {data.school?.name || "School ERP"}
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    Signed in as {data.user.full_name}
                  </p>
                </div>

                <Button
                  type="button"
                  onClick={() => loadDashboard(true)}
                  disabled={refreshing}
                  className="w-full lg:w-auto"
                >
                  <span className="inline-flex items-center justify-center gap-2">
                    <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
                    {refreshing ? "Refreshing..." : "Refresh"}
                  </span>
                </Button>
              </div>
            </div>

            <div className="grid gap-4 p-5 md:grid-cols-3">
              <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  School Code
                </p>
                <p className="mt-1 font-semibold text-slate-900">
                  {data.school?.school_code || "-"}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Role</p>
                <p className="mt-1 font-semibold text-slate-900">{formatRole(data.user.role)}</p>
              </div>
              <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Academic Session
                </p>
                <p className="mt-1 font-semibold text-slate-900">{sessionText}</p>
              </div>
            </div>
          </Card>

          {/* Quick Search */}
          {data.quick_search_enabled && (
            <Card className="mb-6">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h3 className="font-semibold text-slate-900">Quick Search</h3>
                  <p className="text-sm text-slate-500">
                    Find students, teachers, classes, subjects, homework or exams.
                  </p>
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
                          <div className="rounded-xl border border-slate-200 bg-white p-3 transition hover:border-slate-300 hover:shadow-sm">
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                              {result.kind}
                            </p>
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
          )}

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {data.cards.map((card) => {
              const Icon = cardIcons[card.key] || Activity;
              const tone = toneClass[card.tone || "default"] || toneClass.default;
              const accent = toneAccent[card.tone || "default"] || toneAccent.default;
              const rawValue = formatValue(card.value);
              const isLongValue = rawValue.length > 10;
              return (
                <Card
                  key={card.key}
                  className={`border ${accent} transition hover:-translate-y-0.5 hover:shadow-md`}
                >
                  <div className="flex h-full flex-col justify-between gap-3">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium leading-snug text-slate-500">
                        {card.label}
                      </p>
                      <div className={`shrink-0 rounded-2xl p-2.5 ${tone}`}>
                        <Icon size={18} />
                      </div>
                    </div>
                    <p
                      className={`break-all font-bold leading-tight text-slate-900 ${
                        isLongValue ? "text-xl" : "text-3xl"
                      }`}
                    >
                      {rawValue}
                    </p>
                    {card.helper && (
                      <p className="text-xs leading-5 text-slate-400">{card.helper}</p>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>

          {/* ── Bottom section: Charts | Recent Activity, Notices */}
          <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
            <div className="flex flex-col gap-6 xl:col-span-2">
              {data.charts.length > 0 && (
                <div className="grid gap-4 sm:grid-cols-2">
                  {data.charts.map((chart) => (
                    <SimpleBarChart key={chart.title} chart={chart} />
                  ))}
                </div>
              )}

              <NoticeWidget />
            </div>

            {/* Right: Recent Activities */}
            <Card className="h-fit">
              <h3 className="font-semibold text-slate-900">Recent Activities</h3>
              <div className="mt-4 space-y-3">
                {data.recent_activities.length === 0 ? (
                  <p className="text-sm text-slate-500">No recent activity yet.</p>
                ) : (
                  data.recent_activities.map((activity, index) => (
                    <div
                      key={`${activity.kind}-${index}`}
                      className="rounded-2xl border border-slate-100 bg-slate-50 p-3"
                    >
                      <p className="text-sm font-semibold text-slate-900">{activity.title}</p>
                      {activity.description && (
                        <p className="mt-1 text-sm text-slate-500">{activity.description}</p>
                      )}
                      <p className="mt-2 text-xs text-slate-400">
                        {formatDate(activity.created_at)}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>
        </>
      ) : null}
    </AppSection>
  );
}