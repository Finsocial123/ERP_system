"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Plus, ReceiptText, RefreshCw, Trash2 } from "lucide-react";

import { AppSection } from "@/components/CrudManager";
import { Button, Card, Input, Label, Textarea } from "@/components/ui";
import { ACADEMIC_SESSION_CHANGED_EVENT, apiFetch } from "@/lib/api";
import type {
  DailyCollectionReport,
  FeeAssignment,
  FeeCategory,
  FeeDashboard,
  FeeExpense,
  FeeMeta,
  FeePayment,
  FeeReceipt,
  FeeStructure,
  StudentFeeRecord,
} from "@/types";

type TabKey = "dashboard" | "categories" | "structures" | "assign" | "records" | "payments" | "expenses";

type CategoryForm = {
  name: string;
  code: string;
  description: string;
};

type StructureForm = {
  name: string;
  category_id: string;
  academic_session_id: string;
  amount: string;
  due_date: string;
  description: string;
};

type AssignmentForm = {
  fee_structure_id: string;
  academic_session_id: string;
  class_id: string;
  section_id: string;
  student_id: string;
  assigned_amount: string;
  due_date: string;
  note: string;
};

type RecordForm = {
  student_id: string;
  fee_structure_id: string;
  academic_session_id: string;
  title: string;
  amount: string;
  discount_amount: string;
  fine_amount: string;
  due_date: string;
  note: string;
};

type PaymentForm = {
  student_fee_record_id: string;
  amount: string;
  payment_date: string;
  payment_mode: string;
  reference_no: string;
  note: string;
};

type ExpenseForm = {
  title: string;
  category: string;
  amount: string;
  expense_date: string;
  payment_mode: string;
  vendor_name: string;
  reference_no: string;
  note: string;
};

type RecordFilters = {
  class_id: string;
  section_id: string;
  category_id: string;
  fee_type: string;
  status: string;
  search: string;
};

const tabs: { key: TabKey; label: string }[] = [
  { key: "dashboard", label: "Dashboard" },
  { key: "categories", label: "Categories" },
  { key: "structures", label: "Structures" },
  { key: "assign", label: "Assign Fee" },
  { key: "records", label: "Student Records" },
  { key: "payments", label: "Payments" },
  { key: "expenses", label: "Expenses" },
];

const inputClass =
  "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none transition focus:border-slate-400";

const paymentModes = ["CASH", "UPI", "CARD", "BANK_TRANSFER", "CHEQUE", "ONLINE", "OTHER"];
const recordStatusOptions = ["PENDING", "PARTIAL", "PAID", "OVERDUE", "WAIVED"];

const emptyRecordFilters: RecordFilters = {
  class_id: "",
  section_id: "",
  category_id: "",
  fee_type: "",
  status: "",
  search: "",
};

function today() {
  return new Date().toISOString().slice(0, 10);
}

function money(value?: number | null) {
  return `₹${Number(value || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function numberOrNull(value: string) {
  return value === "" ? null : Number(value);
}

function Select({
  value,
  onChange,
  children,
  required = false,
}: {
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
  required?: boolean;
}) {
  return (
    <select
      className={inputClass}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      required={required}
    >
      {children}
    </select>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="p-5 text-sm text-slate-500">{text}</p>;
}

function ScopedLoader({ text = "Refreshing data..." }: { text?: string }) {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center rounded-xl bg-white/75 backdrop-blur-[1px]">
      <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm">
        <Loader2 size={16} className="animate-spin" />
        {text}
      </div>
    </div>
  );
}

function InlineLoader({ text }: { text: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm font-medium text-slate-500">
      <Loader2 size={15} className="animate-spin" />
      {text}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "PAID"
      ? "bg-emerald-50 text-emerald-700"
      : status === "PARTIAL"
        ? "bg-amber-50 text-amber-700"
        : status === "OVERDUE"
          ? "bg-red-50 text-red-700"
          : status === "WAIVED"
            ? "bg-sky-50 text-sky-700"
            : status === "ACTIVE"
              ? "bg-emerald-50 text-emerald-700"
              : status === "INACTIVE"
                ? "bg-red-50 text-red-700"
                : "bg-slate-100 text-slate-700";

  return <span className={`rounded-full px-2 py-1 text-xs font-semibold ${tone}`}>{status}</span>;
}

function SummaryCard({ label, value, helper }: { label: string; value: string | number; helper: string }) {
  const rawValue = String(value);
  const isLong = rawValue.length > 10;

  return (
    <Card>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-2 font-bold text-slate-900 break-all leading-tight ${isLong ? "text-lg" : "text-2xl"}`}>
        {value}
      </p>
      <p className="mt-1 text-xs text-slate-500">{helper}</p>
    </Card>
  );
}

export default function FeeManager() {
  const [activeTab, setActiveTab] = useState<TabKey>("dashboard");

  const [meta, setMeta] = useState<FeeMeta | null>(null);
  const [dashboard, setDashboard] = useState<FeeDashboard | null>(null);
  const [dailyReport, setDailyReport] = useState<DailyCollectionReport | null>(null);
  const [reportDate, setReportDate] = useState(today());

  const [categories, setCategories] = useState<FeeCategory[]>([]);
  const [structures, setStructures] = useState<FeeStructure[]>([]);
  const [assignments, setAssignments] = useState<FeeAssignment[]>([]);
  const [records, setRecords] = useState<StudentFeeRecord[]>([]);
  const [payments, setPayments] = useState<FeePayment[]>([]);
  const [expenses, setExpenses] = useState<FeeExpense[]>([]);
  const [lastReceipt, setLastReceipt] = useState<FeeReceipt | null>(null);

  const [recordFilters, setRecordFilters] = useState<RecordFilters>(emptyRecordFilters);

  const [loading, setLoading] = useState(true);
  const [tabLoading, setTabLoading] = useState<Partial<Record<TabKey, boolean>>>({});
  const [reportLoading, setReportLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [loadedTabs, setLoadedTabs] = useState<Partial<Record<TabKey, boolean>>>({});

  const [categoryForm, setCategoryForm] = useState<CategoryForm>({
    name: "",
    code: "",
    description: "",
  });

  const [structureForm, setStructureForm] = useState<StructureForm>({
    name: "",
    category_id: "",
    academic_session_id: "",
    amount: "",
    due_date: "",
    description: "",
  });

  const [assignmentForm, setAssignmentForm] = useState<AssignmentForm>({
    fee_structure_id: "",
    academic_session_id: "",
    class_id: "",
    section_id: "",
    student_id: "",
    assigned_amount: "",
    due_date: "",
    note: "",
  });

  const [recordForm, setRecordForm] = useState<RecordForm>({
    student_id: "",
    fee_structure_id: "",
    academic_session_id: "",
    title: "",
    amount: "",
    discount_amount: "0",
    fine_amount: "0",
    due_date: "",
    note: "",
  });

  const [paymentForm, setPaymentForm] = useState<PaymentForm>({
    student_fee_record_id: "",
    amount: "",
    payment_date: today(),
    payment_mode: "CASH",
    reference_no: "",
    note: "",
  });

  const [expenseForm, setExpenseForm] = useState<ExpenseForm>({
    title: "",
    category: "",
    amount: "",
    expense_date: today(),
    payment_mode: "CASH",
    vendor_name: "",
    reference_no: "",
    note: "",
  });

  const selectedPaymentRecord = useMemo(
    () => records.find((record) => String(record.id) === paymentForm.student_fee_record_id),
    [paymentForm.student_fee_record_id, records]
  );

  const markLoaded = (tab: TabKey) => {
    setLoadedTabs((previous) => ({ ...previous, [tab]: true }));
  };

  const setTabRefreshing = (tab: TabKey, value: boolean) => {
    setTabLoading((previous) => ({ ...previous, [tab]: value }));
  };

  const currentSessionQuery = (metaData: FeeMeta | null = meta) => {
    const sessionId = metaData?.current_academic_session_id;
    return sessionId ? `academic_session_id=${sessionId}` : "";
  };

  const recordFilterQuery = (filters: RecordFilters = recordFilters) => {
    const params = new URLSearchParams();

    if (filters.class_id) params.set("class_id", filters.class_id);
    if (filters.section_id) params.set("section_id", filters.section_id);
    if (filters.category_id) params.set("category_id", filters.category_id);
    if (filters.fee_type) params.set("fee_type", filters.fee_type);
    if (filters.status) params.set("status", filters.status);
    if (filters.search.trim()) params.set("search", filters.search.trim());

    return params.toString();
  };

  const recordsPath = (filters: RecordFilters = recordFilters) => {
    const query = currentSessionQuery();
    const extra = ["limit=250", recordFilterQuery(filters)].filter(Boolean).join("&");
    const params = [query, extra].filter(Boolean).join("&");

    return params ? `/fees/records?${params}` : "/fees/records";
  };

  const loadDashboardData = async (metaData: FeeMeta | null = meta) => {
    const query = currentSessionQuery(metaData);
    const separator = query ? "&" : "";

    const [dashboardData, reportData] = await Promise.all([
      apiFetch<FeeDashboard>(`/fees/dashboard${query ? `?${query}` : ""}`),
      apiFetch<DailyCollectionReport>(`/fees/daily-collection?${query}${separator}report_date=${reportDate}`),
    ]);

    setDashboard(dashboardData);
    setDailyReport(reportData);
    markLoaded("dashboard");
  };

  const loadTabData = async (tab: TabKey = activeTab, force = false) => {
    if (!force && loadedTabs[tab]) return;

    setTabRefreshing(tab, true);
    setError("");

    try {
      const query = currentSessionQuery();

      const withQuery = (path: string, extra = "") => {
        const params = [query, extra].filter(Boolean).join("&");
        return params ? `${path}?${params}` : path;
      };

      if (tab === "dashboard") {
        await loadDashboardData();
      } else if (tab === "categories") {
        setCategories(await apiFetch<FeeCategory[]>("/fees/categories"));
        markLoaded(tab);
      } else if (tab === "structures") {
        setStructures(await apiFetch<FeeStructure[]>(withQuery("/fees/structures")));
        markLoaded(tab);
      } else if (tab === "assign") {
        setAssignments(await apiFetch<FeeAssignment[]>(withQuery("/fees/assignments")));
        markLoaded(tab);
      } else if (tab === "records") {
        setRecords(await apiFetch<StudentFeeRecord[]>(recordsPath()));
        markLoaded(tab);
      } else if (tab === "payments") {
        const [recordsData, paymentsData] = await Promise.all([
          apiFetch<StudentFeeRecord[]>(withQuery("/fees/records", "status=PENDING&limit=250")),
          apiFetch<FeePayment[]>(withQuery("/fees/payments", "limit=100")),
        ]);

        setRecords(recordsData);
        setPayments(paymentsData);
        markLoaded(tab);
      } else if (tab === "expenses") {
        setExpenses(await apiFetch<FeeExpense[]>(withQuery("/fees/expenses", "limit=100")));
        markLoaded(tab);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load fee data");
    } finally {
      setTabRefreshing(tab, false);
    }
  };

  const loadInitial = async () => {
    setLoading(true);
    setError("");

    try {
      const metaData = await apiFetch<FeeMeta>("/fees/meta");

      setMeta(metaData);

      setStructureForm((prev) => ({
        ...prev,
        academic_session_id: prev.academic_session_id || String(metaData.current_academic_session_id || ""),
      }));

      setAssignmentForm((prev) => ({
        ...prev,
        academic_session_id: prev.academic_session_id || String(metaData.current_academic_session_id || ""),
      }));

      setRecordForm((prev) => ({
        ...prev,
        academic_session_id: prev.academic_session_id || String(metaData.current_academic_session_id || ""),
      }));

      await loadDashboardData(metaData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load fee module");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitial();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const onSessionChanged = () => {
      setLoadedTabs({});
      setRecordFilters(emptyRecordFilters);
      setRecords([]);
      setPayments([]);
      setAssignments([]);
      setStructures([]);

      void (async () => {
        await loadInitial();
        await loadTabData(activeTab, true);
      })();
    };

    window.addEventListener(ACADEMIC_SESSION_CHANGED_EVENT, onSessionChanged);

    return () => window.removeEventListener(ACADEMIC_SESSION_CHANGED_EVENT, onSessionChanged);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  useEffect(() => {
    if (!meta) return;

    loadTabData(activeTab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, meta?.current_academic_session_id]);

  const refreshReport = async () => {
    setReportLoading(true);
    setError("");

    try {
      const query = currentSessionQuery();
      const separator = query ? "&" : "";

      setDailyReport(
        await apiFetch<DailyCollectionReport>(`/fees/daily-collection?${query}${separator}report_date=${reportDate}`)
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load daily report");
    } finally {
      setReportLoading(false);
    }
  };

  const refreshCurrentTab = async () => {
    await loadTabData(activeTab, true);
  };

  const applyRecordFilters = async () => {
    await loadTabData("records", true);
  };

  const clearRecordFilters = async () => {
    setRecordFilters(emptyRecordFilters);
    setTabRefreshing("records", true);
    setError("");

    try {
      setRecords(await apiFetch<StudentFeeRecord[]>(recordsPath(emptyRecordFilters)));
      markLoaded("records");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load fee records");
    } finally {
      setTabRefreshing("records", false);
    }
  };

  const afterSave = async (success: string) => {
    setMessage(success);
    setSaving(false);
    setLoadedTabs({});

    await loadDashboardData();
    await loadTabData(activeTab, true);
  };

  const saveCategory = async (event: React.FormEvent) => {
    event.preventDefault();

    setSaving(true);
    setError("");
    setMessage("");

    try {
      await apiFetch("/fees/categories", {
        method: "POST",
        body: JSON.stringify({
          name: categoryForm.name,
          code: categoryForm.code || null,
          description: categoryForm.description || null,
          is_active: true,
        }),
      });

      setCategoryForm({ name: "", code: "", description: "" });

      await afterSave("Fee category created");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save category");
      setSaving(false);
    }
  };

  const saveStructure = async (event: React.FormEvent) => {
    event.preventDefault();

    setSaving(true);
    setError("");
    setMessage("");

    try {
      await apiFetch("/fees/structures", {
        method: "POST",
        body: JSON.stringify({
          name: structureForm.name,
          category_id: Number(structureForm.category_id),
          academic_session_id: numberOrNull(structureForm.academic_session_id),
          amount: Number(structureForm.amount),
          due_date: structureForm.due_date || null,
          description: structureForm.description || null,
          is_active: true,
        }),
      });

      setStructureForm((prev) => ({
        ...prev,
        name: "",
        category_id: "",
        amount: "",
        due_date: "",
        description: "",
      }));

      await afterSave("Fee structure created");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save structure");
      setSaving(false);
    }
  };

  const saveAssignment = async (event: React.FormEvent) => {
    event.preventDefault();

    setSaving(true);
    setError("");
    setMessage("");

    try {
      await apiFetch("/fees/assignments", {
        method: "POST",
        body: JSON.stringify({
          fee_structure_id: Number(assignmentForm.fee_structure_id),
          academic_session_id: numberOrNull(assignmentForm.academic_session_id),
          class_id: numberOrNull(assignmentForm.class_id),
          section_id: numberOrNull(assignmentForm.section_id),
          student_id: numberOrNull(assignmentForm.student_id),
          assigned_amount: numberOrNull(assignmentForm.assigned_amount),
          due_date: assignmentForm.due_date || null,
          note: assignmentForm.note || null,
          generate_records: true,
        }),
      });

      setAssignmentForm((prev) => ({
        ...prev,
        fee_structure_id: "",
        class_id: "",
        section_id: "",
        student_id: "",
        assigned_amount: "",
        due_date: "",
        note: "",
      }));

      await afterSave("Fee assigned and student records generated");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to assign fee");
      setSaving(false);
    }
  };

  const saveManualRecord = async (event: React.FormEvent) => {
    event.preventDefault();

    setSaving(true);
    setError("");
    setMessage("");

    try {
      await apiFetch("/fees/records", {
        method: "POST",
        body: JSON.stringify({
          student_id: Number(recordForm.student_id),
          fee_structure_id: numberOrNull(recordForm.fee_structure_id),
          academic_session_id: numberOrNull(recordForm.academic_session_id),
          title: recordForm.title,
          amount: Number(recordForm.amount),
          discount_amount: Number(recordForm.discount_amount || 0),
          fine_amount: Number(recordForm.fine_amount || 0),
          due_date: recordForm.due_date || null,
          note: recordForm.note || null,
        }),
      });

      setRecordForm((prev) => ({
        ...prev,
        student_id: "",
        fee_structure_id: "",
        title: "",
        amount: "",
        discount_amount: "0",
        fine_amount: "0",
        due_date: "",
        note: "",
      }));

      await afterSave("Manual student fee record created");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create fee record");
      setSaving(false);
    }
  };

  const savePayment = async (event: React.FormEvent) => {
    event.preventDefault();

    setSaving(true);
    setError("");
    setMessage("");

    try {
      const receipt = await apiFetch<FeeReceipt>("/fees/payments", {
        method: "POST",
        body: JSON.stringify({
          student_fee_record_id: Number(paymentForm.student_fee_record_id),
          amount: Number(paymentForm.amount),
          payment_date: paymentForm.payment_date || null,
          payment_mode: paymentForm.payment_mode,
          reference_no: paymentForm.reference_no || null,
          note: paymentForm.note || null,
        }),
      });

      setLastReceipt(receipt);

      setPaymentForm({
        student_fee_record_id: "",
        amount: "",
        payment_date: today(),
        payment_mode: "CASH",
        reference_no: "",
        note: "",
      });

      await afterSave(`Payment saved. Receipt: ${receipt.payment.receipt_no}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save payment");
      setSaving(false);
    }
  };

  const saveExpense = async (event: React.FormEvent) => {
    event.preventDefault();

    setSaving(true);
    setError("");
    setMessage("");

    try {
      await apiFetch("/fees/expenses", {
        method: "POST",
        body: JSON.stringify({
          title: expenseForm.title,
          category: expenseForm.category || null,
          amount: Number(expenseForm.amount),
          expense_date: expenseForm.expense_date || null,
          payment_mode: expenseForm.payment_mode,
          vendor_name: expenseForm.vendor_name || null,
          reference_no: expenseForm.reference_no || null,
          note: expenseForm.note || null,
        }),
      });

      setExpenseForm({
        title: "",
        category: "",
        amount: "",
        expense_date: today(),
        payment_mode: "CASH",
        vendor_name: "",
        reference_no: "",
        note: "",
      });

      await afterSave("Expense entry saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save expense");
      setSaving(false);
    }
  };

  const deactivate = async (path: string, success: string) => {
    if (!confirm("Are you sure?")) return;

    setError("");
    setMessage("");

    try {
      await apiFetch(path, { method: "DELETE" });
      await afterSave(success);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const openReceipt = async (paymentId: number) => {
    setError("");

    try {
      setLastReceipt(await apiFetch<FeeReceipt>(`/fees/receipts/${paymentId}`));
      setActiveTab("payments");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open receipt");
    }
  };

  const pendingRecords = records.filter((record) => ["PENDING", "PARTIAL", "OVERDUE"].includes(record.status));
  const filteredSections = meta?.sections.filter((section) => !assignmentForm.class_id || section.extra === assignmentForm.class_id) || [];
  const recordFilteredSections = meta?.sections.filter((section) => !recordFilters.class_id || section.extra === recordFilters.class_id) || [];
  const activeRecordFilterCount = Object.values(recordFilters).filter((value) => value.trim() !== "").length;

  const currentTabRefreshing = Boolean(tabLoading[activeTab]);
  const dashboardRefreshing = Boolean(tabLoading.dashboard);
  const recordsRefreshing = Boolean(tabLoading.records);

  return (
    <AppSection
      title="Fee Management"
      description="Create fee categories and structures, assign fees, collect payments, generate receipts, track pending fees and record expenses."
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`rounded-xl px-3 py-2 text-sm font-semibold transition ${
              activeTab === tab.key
                ? "bg-slate-900 text-white"
                : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-100"
            }`}
          >
            {tab.label}
          </button>
        ))}

        <button
          type="button"
          onClick={refreshCurrentTab}
          disabled={loading || currentTabRefreshing}
          className="ml-auto inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw size={15} className={currentTabRefreshing ? "animate-spin" : ""} />
          {currentTabRefreshing ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {error && <p className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {message && <p className="mb-4 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>}

      {loading && !meta ? (
        <Card>
          <InlineLoader text="Loading fee data..." />
        </Card>
      ) : (
        <>
          {activeTab === "dashboard" && dashboard && (
            <div className="space-y-6">
              <div className="relative">
                {dashboardRefreshing && <ScopedLoader text="Refreshing dashboard summary..." />}

                <div className="grid gap-4 md:grid-cols-4">
                  <SummaryCard label="Total Billable" value={money(dashboard.total_billable)} helper="All generated fee records" />
                  <SummaryCard label="Total Paid" value={money(dashboard.total_paid)} helper="Total fee collection" />
                  <SummaryCard label="Pending" value={money(dashboard.total_pending)} helper="Pending/partial/overdue balance" />
                  <SummaryCard label="Today Collection" value={money(dashboard.today_collection)} helper="Payments collected today" />
                  <SummaryCard label="Month Collection" value={money(dashboard.month_collection)} helper="Current month income" />
                  <SummaryCard label="Month Expense" value={money(dashboard.month_expense)} helper="Current month expenses" />
                  <SummaryCard label="Net Month" value={money(dashboard.net_month_collection)} helper="Collection minus expenses" />
                  <SummaryCard label="Overdue Records" value={dashboard.overdue_records} helper="Records past due date" />
                </div>
              </div>

              <Card className="relative">
                {(dashboardRefreshing || reportLoading) && <ScopedLoader text="Loading daily collection report..." />}

                <div className="mb-4 flex flex-wrap items-end gap-3">
                  <div>
                    <Label>Daily collection date</Label>
                    <Input type="date" value={reportDate} onChange={(event) => setReportDate(event.target.value)} />
                  </div>

                  <Button type="button" onClick={refreshReport} disabled={reportLoading || dashboardRefreshing}>
                    <span className="inline-flex items-center gap-2">
                      {reportLoading && <Loader2 size={15} className="animate-spin" />}
                      Load Report
                    </span>
                  </Button>
                </div>

                <h2 className="font-semibold text-slate-900">Daily Collection Report</h2>

                <p className="mt-1 text-sm text-slate-500">
                  {dailyReport
                    ? `${dailyReport.total_payments} payments · ${money(dailyReport.total_collection)} collected`
                    : "No report loaded"}
                </p>

                {dailyReport && Object.keys(dailyReport.payment_mode_summary).length > 0 && (
                  <div className="mt-4 grid gap-3 md:grid-cols-4">
                    {Object.entries(dailyReport.payment_mode_summary).map(([mode, amount]) => (
                      <div key={mode} className="rounded-xl border border-slate-200 p-3">
                        <p className="text-xs uppercase text-slate-400">{mode}</p>
                        <p className="font-bold text-slate-900">{money(amount)}</p>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          )}

          {activeTab === "categories" && (
            <div className="space-y-6">
              <Card>
                <form onSubmit={saveCategory} className="grid gap-4 md:grid-cols-3">
                  <div>
                    <Label>Category Name</Label>
                    <Input
                      value={categoryForm.name}
                      onChange={(event) => setCategoryForm((prev) => ({ ...prev, name: event.target.value }))}
                      placeholder="Tuition Fee"
                      required
                    />
                  </div>

                  <div>
                    <Label>Code</Label>
                    <Input
                      value={categoryForm.code}
                      onChange={(event) => setCategoryForm((prev) => ({ ...prev, code: event.target.value }))}
                      placeholder="TUTION"
                    />
                  </div>

                  <div className="md:col-span-3">
                    <Label>Description</Label>
                    <Textarea
                      value={categoryForm.description}
                      onChange={(event) => setCategoryForm((prev) => ({ ...prev, description: event.target.value }))}
                      placeholder="Optional notes"
                    />
                  </div>

                  <div className="md:col-span-3">
                    <Button type="submit" disabled={saving}>
                      <span className="inline-flex items-center gap-2">
                        {saving ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                        Create Category
                      </span>
                    </Button>
                  </div>
                </form>
              </Card>

              <TableWrap
                empty={categories.length === 0}
                emptyText="No fee category yet."
                loading={Boolean(tabLoading.categories)}
                loadingText="Refreshing fee categories..."
              >
                <thead className="bg-slate-100 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Name</th>
                    <th className="px-4 py-3">Code</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {categories.map((category) => (
                    <tr key={category.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-medium text-slate-900">{category.name}</td>
                      <td className="px-4 py-3 text-slate-700">{category.code || "-"}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={category.is_active ? "ACTIVE" : "INACTIVE"} />
                      </td>
                      <td className="px-4 py-3">
                        <IconButton onClick={() => deactivate(`/fees/categories/${category.id}`, "Category deactivated")} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableWrap>
            </div>
          )}

          {activeTab === "structures" && (
            <div className="space-y-6">
              <Card>
                <form onSubmit={saveStructure} className="grid gap-4 md:grid-cols-3">
                  <div>
                    <Label>Fee Name</Label>
                    <Input
                      value={structureForm.name}
                      onChange={(event) => setStructureForm((prev) => ({ ...prev, name: event.target.value }))}
                      placeholder="April Tuition Fee"
                      required
                    />
                  </div>

                  <div>
                    <Label>Category</Label>
                    <Select
                      value={structureForm.category_id}
                      onChange={(value) => setStructureForm((prev) => ({ ...prev, category_id: value }))}
                      required
                    >
                      <option value="">Select category</option>
                      {meta?.categories.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Academic Session</Label>
                    <Select
                      value={structureForm.academic_session_id}
                      onChange={(value) => setStructureForm((prev) => ({ ...prev, academic_session_id: value }))}
                    >
                      <option value="">Optional</option>
                      {meta?.academic_sessions.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Amount</Label>
                    <Input
                      type="number"
                      min="1"
                      step="0.01"
                      value={structureForm.amount}
                      onChange={(event) => setStructureForm((prev) => ({ ...prev, amount: event.target.value }))}
                      required
                    />
                  </div>

                  <div>
                    <Label>Due Date</Label>
                    <Input
                      type="date"
                      value={structureForm.due_date}
                      onChange={(event) => setStructureForm((prev) => ({ ...prev, due_date: event.target.value }))}
                    />
                  </div>

                  <div className="md:col-span-3">
                    <Label>Description</Label>
                    <Textarea
                      value={structureForm.description}
                      onChange={(event) => setStructureForm((prev) => ({ ...prev, description: event.target.value }))}
                    />
                  </div>

                  <div className="md:col-span-3">
                    <Button type="submit" disabled={saving}>
                      <span className="inline-flex items-center gap-2">
                        {saving ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                        Create Structure
                      </span>
                    </Button>
                  </div>
                </form>
              </Card>

              <TableWrap
                empty={structures.length === 0}
                emptyText="No fee structure yet."
                loading={Boolean(tabLoading.structures)}
                loadingText="Refreshing fee structures..."
              >
                <thead className="bg-slate-100 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Fee</th>
                    <th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">Amount</th>
                    <th className="px-4 py-3">Due Date</th>
                    <th className="px-4 py-3">Session</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {structures.map((structure) => (
                    <tr key={structure.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-medium text-slate-900">{structure.name}</td>
                      <td className="px-4 py-3 text-slate-700">{structure.category_name || "-"}</td>
                      <td className="px-4 py-3 text-slate-700">{money(structure.amount)}</td>
                      <td className="px-4 py-3 text-slate-700">{structure.due_date || "-"}</td>
                      <td className="px-4 py-3 text-slate-700">{structure.academic_session_name || "-"}</td>
                      <td className="px-4 py-3">
                        <IconButton onClick={() => deactivate(`/fees/structures/${structure.id}`, "Structure deactivated")} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableWrap>
            </div>
          )}

          {activeTab === "assign" && (
            <div className="space-y-6">
              <Card>
                <form onSubmit={saveAssignment} className="grid gap-4 md:grid-cols-3">
                  <div>
                    <Label>Fee Structure</Label>
                    <Select
                      value={assignmentForm.fee_structure_id}
                      onChange={(value) => setAssignmentForm((prev) => ({ ...prev, fee_structure_id: value }))}
                      required
                    >
                      <option value="">Select fee</option>
                      {meta?.structures.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name} {item.extra ? `· ${item.extra}` : ""}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Academic Session</Label>
                    <Select
                      value={assignmentForm.academic_session_id}
                      onChange={(value) => setAssignmentForm((prev) => ({ ...prev, academic_session_id: value }))}
                    >
                      <option value="">Optional</option>
                      {meta?.academic_sessions.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Override Amount</Label>
                    <Input
                      type="number"
                      min="1"
                      step="0.01"
                      value={assignmentForm.assigned_amount}
                      onChange={(event) => setAssignmentForm((prev) => ({ ...prev, assigned_amount: event.target.value }))}
                      placeholder="Keep blank to use structure amount"
                    />
                  </div>

                  <div>
                    <Label>Assign to Class</Label>
                    <Select
                      value={assignmentForm.class_id}
                      onChange={(value) =>
                        setAssignmentForm((prev) => ({
                          ...prev,
                          class_id: value,
                          student_id: "",
                          section_id: "",
                        }))
                      }
                    >
                      <option value="">No class</option>
                      {meta?.classes.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Section</Label>
                    <Select
                      value={assignmentForm.section_id}
                      onChange={(value) => setAssignmentForm((prev) => ({ ...prev, section_id: value }))}
                    >
                      <option value="">All sections</option>
                      {filteredSections.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Or Assign to Student</Label>
                    <Select
                      value={assignmentForm.student_id}
                      onChange={(value) =>
                        setAssignmentForm((prev) => ({
                          ...prev,
                          student_id: value,
                          class_id: "",
                          section_id: "",
                        }))
                      }
                    >
                      <option value="">No individual student</option>
                      {meta?.students.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name} · {item.extra}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Override Due Date</Label>
                    <Input
                      type="date"
                      value={assignmentForm.due_date}
                      onChange={(event) => setAssignmentForm((prev) => ({ ...prev, due_date: event.target.value }))}
                    />
                  </div>

                  <div className="md:col-span-3">
                    <Label>Note</Label>
                    <Textarea
                      value={assignmentForm.note}
                      onChange={(event) => setAssignmentForm((prev) => ({ ...prev, note: event.target.value }))}
                      placeholder="Optional note shown in generated records"
                    />
                  </div>

                  <div className="md:col-span-3">
                    <Button type="submit" disabled={saving}>
                      <span className="inline-flex items-center gap-2">
                        {saving ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                        Assign & Generate Records
                      </span>
                    </Button>
                  </div>
                </form>
              </Card>

              <TableWrap
                empty={assignments.length === 0}
                emptyText="No fee assignments yet."
                loading={Boolean(tabLoading.assign)}
                loadingText="Refreshing fee assignments..."
              >
                <thead className="bg-slate-100 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Fee</th>
                    <th className="px-4 py-3">Assigned To</th>
                    <th className="px-4 py-3">Amount</th>
                    <th className="px-4 py-3">Due</th>
                    <th className="px-4 py-3">Records</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {assignments.map((assignment) => (
                    <tr key={assignment.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-medium text-slate-900">{assignment.fee_structure_name || "-"}</td>
                      <td className="px-4 py-3 text-slate-700">
                        {assignment.student_name ||
                          [assignment.class_name, assignment.section_name || "All sections"].filter(Boolean).join(" · ") ||
                          "-"}
                      </td>
                      <td className="px-4 py-3 text-slate-700">
                        {assignment.assigned_amount ? money(assignment.assigned_amount) : "Structure amount"}
                      </td>
                      <td className="px-4 py-3 text-slate-700">{assignment.due_date || "Structure due date"}</td>
                      <td className="px-4 py-3 text-slate-700">{assignment.generated_records_count}</td>
                      <td className="px-4 py-3">
                        <IconButton onClick={() => deactivate(`/fees/assignments/${assignment.id}`, "Assignment deactivated")} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableWrap>
            </div>
          )}

          {activeTab === "records" && (
            <div className="space-y-6">
              <Card>
                <h2 className="mb-4 font-semibold text-slate-900">Manual Student Fee Record</h2>

                <form onSubmit={saveManualRecord} className="grid gap-4 md:grid-cols-3">
                  <div>
                    <Label>Student</Label>
                    <Select
                      value={recordForm.student_id}
                      onChange={(value) => setRecordForm((prev) => ({ ...prev, student_id: value }))}
                      required
                    >
                      <option value="">Select student</option>
                      {meta?.students.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name} · {item.extra}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Linked Structure</Label>
                    <Select
                      value={recordForm.fee_structure_id}
                      onChange={(value) => setRecordForm((prev) => ({ ...prev, fee_structure_id: value }))}
                    >
                      <option value="">Optional</option>
                      {meta?.structures.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Academic Session</Label>
                    <Select
                      value={recordForm.academic_session_id}
                      onChange={(value) => setRecordForm((prev) => ({ ...prev, academic_session_id: value }))}
                    >
                      <option value="">Optional</option>
                      {meta?.academic_sessions.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Title</Label>
                    <Input
                      value={recordForm.title}
                      onChange={(event) => setRecordForm((prev) => ({ ...prev, title: event.target.value }))}
                      placeholder="Bus Fee / Extra Lab Fee"
                      required
                    />
                  </div>

                  <div>
                    <Label>Amount</Label>
                    <Input
                      type="number"
                      min="1"
                      step="0.01"
                      value={recordForm.amount}
                      onChange={(event) => setRecordForm((prev) => ({ ...prev, amount: event.target.value }))}
                      required
                    />
                  </div>

                  <div>
                    <Label>Due Date</Label>
                    <Input
                      type="date"
                      value={recordForm.due_date}
                      onChange={(event) => setRecordForm((prev) => ({ ...prev, due_date: event.target.value }))}
                    />
                  </div>

                  <div>
                    <Label>Discount</Label>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      value={recordForm.discount_amount}
                      onChange={(event) => setRecordForm((prev) => ({ ...prev, discount_amount: event.target.value }))}
                    />
                  </div>

                  <div>
                    <Label>Fine</Label>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      value={recordForm.fine_amount}
                      onChange={(event) => setRecordForm((prev) => ({ ...prev, fine_amount: event.target.value }))}
                    />
                  </div>

                  <div className="md:col-span-3">
                    <Label>Note</Label>
                    <Textarea
                      value={recordForm.note}
                      onChange={(event) => setRecordForm((prev) => ({ ...prev, note: event.target.value }))}
                    />
                  </div>

                  <div className="md:col-span-3">
                    <Button type="submit" disabled={saving}>
                      <span className="inline-flex items-center gap-2">
                        {saving && <Loader2 size={16} className="animate-spin" />}
                        Create Record
                      </span>
                    </Button>
                  </div>
                </form>
              </Card>

              <Card>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h2 className="font-semibold text-slate-900">Filter Student Fee Records</h2>
                    <p className="text-sm text-slate-500">
                      Separate records by class, category, annual/midterm fee category, manual miscellaneous fee, status or student
                      name/admission no.
                    </p>
                  </div>

                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                    {records.length} shown{activeRecordFilterCount ? ` · ${activeRecordFilterCount} filters` : ""}
                  </span>
                </div>

                <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
                  <div>
                    <Label>Class</Label>
                    <Select
                      value={recordFilters.class_id}
                      onChange={(value) =>
                        setRecordFilters((prev) => ({
                          ...prev,
                          class_id: value,
                          section_id: "",
                        }))
                      }
                    >
                      <option value="">All classes</option>
                      {meta?.classes.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Section</Label>
                    <Select
                      value={recordFilters.section_id}
                      onChange={(value) => setRecordFilters((prev) => ({ ...prev, section_id: value }))}
                    >
                      <option value="">All sections</option>
                      {recordFilteredSections.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Fee Category</Label>
                    <Select
                      value={recordFilters.category_id}
                      onChange={(value) =>
                        setRecordFilters((prev) => ({
                          ...prev,
                          category_id: value,
                          fee_type: value ? "STRUCTURED" : prev.fee_type,
                        }))
                      }
                    >
                      <option value="">All categories</option>
                      {meta?.categories.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Record Type</Label>
                    <Select
                      value={recordFilters.fee_type}
                      onChange={(value) =>
                        setRecordFilters((prev) => ({
                          ...prev,
                          fee_type: value,
                          category_id: value === "MISCELLANEOUS" ? "" : prev.category_id,
                        }))
                      }
                    >
                      <option value="">All records</option>
                      <option value="STRUCTURED">Structured/category fees</option>
                      <option value="MISCELLANEOUS">Miscellaneous/manual fees</option>
                    </Select>
                  </div>

                  <div>
                    <Label>Status</Label>
                    <Select
                      value={recordFilters.status}
                      onChange={(value) => setRecordFilters((prev) => ({ ...prev, status: value }))}
                    >
                      <option value="">All statuses</option>
                      {recordStatusOptions.map((status) => (
                        <option key={status} value={status}>
                          {status}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Search</Label>
                    <Input
                      value={recordFilters.search}
                      onChange={(event) => setRecordFilters((prev) => ({ ...prev, search: event.target.value }))}
                      placeholder="Student / fee / admission"
                    />
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <Button type="button" onClick={applyRecordFilters} disabled={recordsRefreshing}>
                    <span className="inline-flex items-center gap-2">
                      {recordsRefreshing && <Loader2 size={15} className="animate-spin" />}
                      Apply Filters
                    </span>
                  </Button>

                  <button
                    type="button"
                    onClick={clearRecordFilters}
                    disabled={recordsRefreshing}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Clear
                  </button>
                </div>
              </Card>

              <RecordsTable
                records={records}
                loading={recordsRefreshing}
                onPay={(record) => {
                  setActiveTab("payments");
                  setPaymentForm((prev) => ({
                    ...prev,
                    student_fee_record_id: String(record.id),
                    amount: String(record.balance_amount),
                  }));
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              />
            </div>
          )}

          {activeTab === "payments" && (
            <div className="space-y-6">
              {lastReceipt && (
                <Card>
                  <h2 className="flex items-center gap-2 font-semibold text-slate-900">
                    <ReceiptText size={18} />
                    Receipt Generated
                  </h2>

                  <div className="mt-4 grid gap-3 md:grid-cols-3">
                    <p className="text-sm">
                      <span className="text-slate-500">Receipt:</span> <b>{lastReceipt.payment.receipt_no}</b>
                    </p>
                    <p className="text-sm">
                      <span className="text-slate-500">Student:</span> <b>{lastReceipt.payment.student_name}</b>
                    </p>
                    <p className="text-sm">
                      <span className="text-slate-500">Amount:</span> <b>{money(lastReceipt.payment.amount)}</b>
                    </p>
                    <p className="text-sm">
                      <span className="text-slate-500">Fee:</span> <b>{lastReceipt.record.title}</b>
                    </p>
                    <p className="text-sm">
                      <span className="text-slate-500">Paid:</span> <b>{money(lastReceipt.record.paid_amount)}</b>
                    </p>
                    <p className="text-sm">
                      <span className="text-slate-500">Balance:</span> <b>{money(lastReceipt.record.balance_amount)}</b>
                    </p>
                  </div>
                </Card>
              )}

              <Card>
                <h2 className="mb-4 font-semibold text-slate-900">Payment Entry</h2>

                <form onSubmit={savePayment} className="grid gap-4 md:grid-cols-3">
                  <div className="md:col-span-2">
                    <Label>Pending Fee Record</Label>
                    <Select
                      value={paymentForm.student_fee_record_id}
                      onChange={(value) =>
                        setPaymentForm((prev) => ({
                          ...prev,
                          student_fee_record_id: value,
                          amount: String(records.find((item) => String(item.id) === value)?.balance_amount || ""),
                        }))
                      }
                      required
                    >
                      <option value="">Select pending fee</option>
                      {pendingRecords.map((record) => (
                        <option key={record.id} value={record.id}>
                          {record.student_name} · {record.title} · Balance {money(record.balance_amount)}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Amount</Label>
                    <Input
                      type="number"
                      min="1"
                      step="0.01"
                      max={selectedPaymentRecord?.balance_amount || undefined}
                      value={paymentForm.amount}
                      onChange={(event) => setPaymentForm((prev) => ({ ...prev, amount: event.target.value }))}
                      required
                    />
                  </div>

                  <div>
                    <Label>Payment Date</Label>
                    <Input
                      type="date"
                      value={paymentForm.payment_date}
                      onChange={(event) => setPaymentForm((prev) => ({ ...prev, payment_date: event.target.value }))}
                    />
                  </div>

                  <div>
                    <Label>Payment Mode</Label>
                    <Select
                      value={paymentForm.payment_mode}
                      onChange={(value) => setPaymentForm((prev) => ({ ...prev, payment_mode: value }))}
                      required
                    >
                      {paymentModes.map((mode) => (
                        <option key={mode} value={mode}>
                          {mode}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Reference No.</Label>
                    <Input
                      value={paymentForm.reference_no}
                      onChange={(event) => setPaymentForm((prev) => ({ ...prev, reference_no: event.target.value }))}
                      placeholder="UPI ref / cheque no."
                    />
                  </div>

                  <div className="md:col-span-3">
                    <Label>Note</Label>
                    <Textarea
                      value={paymentForm.note}
                      onChange={(event) => setPaymentForm((prev) => ({ ...prev, note: event.target.value }))}
                    />
                  </div>

                  <div className="md:col-span-3">
                    <Button type="submit" disabled={saving}>
                      <span className="inline-flex items-center gap-2">
                        {saving && <Loader2 size={16} className="animate-spin" />}
                        Save Payment & Generate Receipt
                      </span>
                    </Button>
                  </div>
                </form>
              </Card>

              <PaymentsTable payments={payments} loading={Boolean(tabLoading.payments)} onReceipt={openReceipt} />
            </div>
          )}

          {activeTab === "expenses" && (
            <div className="space-y-6">
              <Card>
                <form onSubmit={saveExpense} className="grid gap-4 md:grid-cols-3">
                  <div>
                    <Label>Expense Title</Label>
                    <Input
                      value={expenseForm.title}
                      onChange={(event) => setExpenseForm((prev) => ({ ...prev, title: event.target.value }))}
                      placeholder="Electricity bill"
                      required
                    />
                  </div>

                  <div>
                    <Label>Category</Label>
                    <Input
                      value={expenseForm.category}
                      onChange={(event) => setExpenseForm((prev) => ({ ...prev, category: event.target.value }))}
                      placeholder="Utilities"
                    />
                  </div>

                  <div>
                    <Label>Amount</Label>
                    <Input
                      type="number"
                      min="1"
                      step="0.01"
                      value={expenseForm.amount}
                      onChange={(event) => setExpenseForm((prev) => ({ ...prev, amount: event.target.value }))}
                      required
                    />
                  </div>

                  <div>
                    <Label>Expense Date</Label>
                    <Input
                      type="date"
                      value={expenseForm.expense_date}
                      onChange={(event) => setExpenseForm((prev) => ({ ...prev, expense_date: event.target.value }))}
                    />
                  </div>

                  <div>
                    <Label>Payment Mode</Label>
                    <Select
                      value={expenseForm.payment_mode}
                      onChange={(value) => setExpenseForm((prev) => ({ ...prev, payment_mode: value }))}
                    >
                      {paymentModes.map((mode) => (
                        <option key={mode} value={mode}>
                          {mode}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Label>Vendor</Label>
                    <Input
                      value={expenseForm.vendor_name}
                      onChange={(event) => setExpenseForm((prev) => ({ ...prev, vendor_name: event.target.value }))}
                    />
                  </div>

                  <div>
                    <Label>Reference No.</Label>
                    <Input
                      value={expenseForm.reference_no}
                      onChange={(event) => setExpenseForm((prev) => ({ ...prev, reference_no: event.target.value }))}
                    />
                  </div>

                  <div className="md:col-span-3">
                    <Label>Note</Label>
                    <Textarea
                      value={expenseForm.note}
                      onChange={(event) => setExpenseForm((prev) => ({ ...prev, note: event.target.value }))}
                    />
                  </div>

                  <div className="md:col-span-3">
                    <Button type="submit" disabled={saving}>
                      <span className="inline-flex items-center gap-2">
                        {saving && <Loader2 size={16} className="animate-spin" />}
                        Save Expense
                      </span>
                    </Button>
                  </div>
                </form>
              </Card>

              <TableWrap
                empty={expenses.length === 0}
                emptyText="No expense entries yet."
                loading={Boolean(tabLoading.expenses)}
                loadingText="Refreshing expenses..."
              >
                <thead className="bg-slate-100 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Title</th>
                    <th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3">Mode</th>
                    <th className="px-4 py-3">Amount</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {expenses.map((expense) => (
                    <tr key={expense.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-medium text-slate-900">{expense.title}</td>
                      <td className="px-4 py-3 text-slate-700">{expense.category || "-"}</td>
                      <td className="px-4 py-3 text-slate-700">{expense.expense_date}</td>
                      <td className="px-4 py-3 text-slate-700">{expense.payment_mode}</td>
                      <td className="px-4 py-3 text-red-700">{money(expense.amount)}</td>
                      <td className="px-4 py-3">
                        <IconButton onClick={() => deactivate(`/fees/expenses/${expense.id}`, "Expense deactivated")} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableWrap>
            </div>
          )}
        </>
      )}
    </AppSection>
  );
}

function TableWrap({
  empty,
  emptyText,
  loading = false,
  loadingText = "Refreshing data...",
  children,
}: {
  empty: boolean;
  emptyText: string;
  loading?: boolean;
  loadingText?: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="relative overflow-hidden p-0">
      {loading && <ScopedLoader text={loadingText} />}

      {empty && !loading ? (
        <Empty text={emptyText} />
      ) : (
        <div className={`overflow-x-auto transition ${loading ? "opacity-60" : "opacity-100"}`}>
          <table className="w-full text-left text-sm">{children}</table>
        </div>
      )}
    </Card>
  );
}

function IconButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="rounded-lg border border-red-200 p-2 text-red-600 hover:bg-red-50">
      <Trash2 size={15} />
    </button>
  );
}

function RecordsTable({
  records,
  loading = false,
  onPay,
}: {
  records: StudentFeeRecord[];
  loading?: boolean;
  onPay: (record: StudentFeeRecord) => void;
}) {
  return (
    <TableWrap
      empty={records.length === 0}
      emptyText="No student fee records yet."
      loading={loading}
      loadingText="Refreshing student fee records..."
    >
      <thead className="bg-slate-100 text-xs uppercase text-slate-500">
        <tr>
          <th className="px-4 py-3">Student</th>
          <th className="px-4 py-3">Fee</th>
          <th className="px-4 py-3">Category</th>
          <th className="px-4 py-3">Due</th>
          <th className="px-4 py-3">Billable</th>
          <th className="px-4 py-3">Paid</th>
          <th className="px-4 py-3">Balance</th>
          <th className="px-4 py-3">Status</th>
          <th className="px-4 py-3">Action</th>
        </tr>
      </thead>

      <tbody className="divide-y divide-slate-100">
        {records.map((record) => (
          <tr key={record.id} className="hover:bg-slate-50">
            <td className="px-4 py-3">
              <p className="font-medium text-slate-900">{record.student_name || "-"}</p>
              <p className="text-xs text-slate-500">
                {record.admission_no || "-"} · {record.class_name || "-"}
                {record.section_name ? `-${record.section_name}` : ""}
              </p>
            </td>

            <td className="px-4 py-3 text-slate-700">{record.title}</td>

            <td className="px-4 py-3 text-slate-700">
              {record.category_name || (record.fee_type === "MISCELLANEOUS" ? "Miscellaneous" : "-")}
            </td>

            <td className="px-4 py-3 text-slate-700">{record.due_date || "-"}</td>
            <td className="px-4 py-3 text-slate-700">{money(record.amount + record.fine_amount - record.discount_amount)}</td>
            <td className="px-4 py-3 text-emerald-700">{money(record.paid_amount)}</td>
            <td className="px-4 py-3 text-amber-700">{money(record.balance_amount)}</td>

            <td className="px-4 py-3">
              <StatusBadge status={record.status} />
            </td>

            <td className="px-4 py-3">
              {record.balance_amount > 0 && record.status !== "WAIVED" ? (
                <button
                  type="button"
                  onClick={() => onPay(record)}
                  className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold hover:bg-slate-100"
                >
                  Pay
                </button>
              ) : (
                "-"
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </TableWrap>
  );
}

function PaymentsTable({
  payments,
  loading = false,
  onReceipt,
}: {
  payments: FeePayment[];
  loading?: boolean;
  onReceipt: (paymentId: number) => void;
}) {
  return (
    <TableWrap empty={payments.length === 0} emptyText="No payments yet." loading={loading} loadingText="Refreshing payments...">
      <thead className="bg-slate-100 text-xs uppercase text-slate-500">
        <tr>
          <th className="px-4 py-3">Receipt</th>
          <th className="px-4 py-3">Student</th>
          <th className="px-4 py-3">Fee</th>
          <th className="px-4 py-3">Date</th>
          <th className="px-4 py-3">Mode</th>
          <th className="px-4 py-3">Amount</th>
          <th className="px-4 py-3">Action</th>
        </tr>
      </thead>

      <tbody className="divide-y divide-slate-100">
        {payments.map((payment) => (
          <tr key={payment.id} className="hover:bg-slate-50">
            <td className="px-4 py-3 font-medium text-slate-900">{payment.receipt_no}</td>
            <td className="px-4 py-3 text-slate-700">{payment.student_name || "-"}</td>
            <td className="px-4 py-3 text-slate-700">{payment.fee_title || "-"}</td>
            <td className="px-4 py-3 text-slate-700">{payment.payment_date}</td>
            <td className="px-4 py-3 text-slate-700">{payment.payment_mode}</td>
            <td className="px-4 py-3 text-emerald-700">{money(payment.amount)}</td>
            <td className="px-4 py-3">
              <button
                type="button"
                onClick={() => onReceipt(payment.id)}
                className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold hover:bg-slate-100"
              >
                Receipt
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </TableWrap>
  );
}