"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle, BookOpen, CheckCircle2, ChevronDown, ChevronUp,
  IndianRupee, Library, Loader2, Plus, RefreshCw, Search,
  Trash2, X, BookMarked, RotateCcw, ShieldAlert,
} from "lucide-react";

import AppShell from "@/components/AppShell";
import { Button, Card, Input, Label } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { getSavedAuth } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────
type Book = {
  id: number; title: string; author: string; isbn?: string | null;
  publisher?: string | null; edition?: string | null; category?: string | null;
  language: string; shelf_location?: string | null; description?: string | null;
  cover_url?: string | null; total_copies: number; available_copies: number; is_active: boolean;
};

type Issue = {
  id: number; book_id: number; book_title: string; book_isbn?: string | null;
  student_id?: number | null; teacher_id?: number | null; borrower_name: string;
  issue_date: string; due_date: string; return_date?: string | null;
  status: string; fine_per_day: number; fine_amount: number; fine_paid: boolean;
  notes?: string | null; days_overdue: number;
};

type Stats = {
  total_books: number; total_copies: number; available_copies: number;
  issued_count: number; overdue_count: number; total_fine_pending: number;
};

type Student = { id: number; first_name: string; last_name?: string | null; admission_no: string };
type Teacher = { id: number; full_name: string; employee_id: string };

// ── Helpers ────────────────────────────────────────────────────────────────
const STATUS_META: Record<string, { color: string; label: string }> = {
  ISSUED:   { color: "bg-blue-100 text-blue-700",   label: "Issued" },
  RETURNED: { color: "bg-emerald-100 text-emerald-700", label: "Returned" },
  OVERDUE:  { color: "bg-red-100 text-red-700",     label: "Overdue" },
  LOST:     { color: "bg-slate-100 text-slate-600", label: "Lost" },
};

function fmt(d: string) {
  return new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function today() { return new Date().toISOString().split("T")[0]; }

function dueIn(dueDate: string): string {
  const diff = Math.ceil((new Date(dueDate).getTime() - Date.now()) / 86400000);
  if (diff < 0) return `${Math.abs(diff)} days overdue`;
  if (diff === 0) return "Due today";
  return `Due in ${diff} days`;
}

// ── Reusable Modal ──────────────────────────────────────────────────────────
function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <h2 className="text-base font-semibold text-slate-900">{title}</h2>
          <button onClick={onClose} className="rounded-lg p-1 hover:bg-slate-100"><X size={18} /></button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

// ── Stat Card ───────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: string }) {
  return (
    <Card>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent || "text-slate-900"}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
    </Card>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ══════════════════════════════════════════════════════════════════════════════
export default function LibraryPage() {
  const role = getSavedAuth()?.user?.role ?? "";
  const isAdmin = ["SUPER_ADMIN", "SCHOOL_OWNER", "SCHOOL_ADMIN"].includes(role);
  const isStaff = isAdmin || role === "TEACHER";

  const [tab, setTab] = useState<"books" | "issues" | "overdue" | "my">("books");
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  // Books tab
  const [books, setBooks] = useState<Book[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [catFilter, setCatFilter] = useState("");
  const [availOnly, setAvailOnly] = useState(false);
  const [loadingBooks, setLoadingBooks] = useState(false);

  // Issues tab
  const [issues, setIssues] = useState<Issue[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [loadingIssues, setLoadingIssues] = useState(false);

  // Overdue tab
  const [overdue, setOverdue] = useState<Issue[]>([]);
  const [loadingOverdue, setLoadingOverdue] = useState(false);

  // My issues tab (student/teacher)
  const [myIssues, setMyIssues] = useState<Issue[]>([]);
  const [loadingMy, setLoadingMy] = useState(false);

  // Modals
  const [showAddBook, setShowAddBook] = useState(false);
  const [showEditBook, setShowEditBook] = useState<Book | null>(null);
  const [showIssueModal, setShowIssueModal] = useState<Book | null>(null);
  const [showReturnModal, setShowReturnModal] = useState<Issue | null>(null);
  const [expandedIssue, setExpandedIssue] = useState<number | null>(null);

  // Borrower search
  const [students, setStudents] = useState<Student[]>([]);
  const [teachers, setTeachers] = useState<Teacher[]>([]);

  const err = (e: unknown) => setError(e instanceof Error ? e.message : "Something went wrong");

  useEffect(() => {
    loadStats();
    loadCategories();
    loadBooks();
    if (isStaff) { loadStudents(); loadTeachers(); }
  }, []);

  useEffect(() => { if (tab === "books") loadBooks(); }, [search, catFilter, availOnly]);
  useEffect(() => { if (tab === "issues" && isStaff) loadIssues(); }, [tab, statusFilter]);
  useEffect(() => { if (tab === "overdue" && isStaff) loadOverdue(); }, [tab]);
  useEffect(() => { if (tab === "my") loadMyIssues(); }, [tab]);

  const loadStats = () => isStaff && apiFetch<Stats>("/library/stats").then(setStats).catch(() => {});
  const loadCategories = () => apiFetch<string[]>("/library/categories").then(setCategories).catch(() => {});
  const loadBooks = () => {
    setLoadingBooks(true);
    const p = new URLSearchParams();
    if (search) p.set("search", search);
    if (catFilter) p.set("category", catFilter);
    if (availOnly) p.set("available_only", "true");
    apiFetch<Book[]>(`/library/books?${p}`).then(setBooks).catch(err).finally(() => setLoadingBooks(false));
  };
  const loadIssues = () => {
    setLoadingIssues(true);
    const p = new URLSearchParams();
    if (statusFilter) p.set("status", statusFilter);
    apiFetch<Issue[]>(`/library/issues?${p}`).then(setIssues).catch(err).finally(() => setLoadingIssues(false));
  };
  const loadOverdue = () => {
    setLoadingOverdue(true);
    apiFetch<Issue[]>("/library/issues/overdue").then(setOverdue).catch(err).finally(() => setLoadingOverdue(false));
  };
  const loadMyIssues = () => {
    setLoadingMy(true);
    apiFetch<Issue[]>("/library/issues/my").then(setMyIssues).catch(err).finally(() => setLoadingMy(false));
  };
  const loadStudents = () => apiFetch<Student[]>("/students").then(setStudents).catch(() => {});
  const loadTeachers = () => apiFetch<Teacher[]>("/teachers").then(setTeachers).catch(() => {});

  const handlePayFine = async (issueId: number) => {
    try {
      await apiFetch(`/library/issues/${issueId}/pay-fine`, { method: "POST", body: JSON.stringify({ fine_paid: true }) });
      loadIssues(); loadOverdue(); loadStats();
    } catch (e) { err(e); }
  };

  const handleDeactivate = async (bookId: number) => {
    if (!confirm("Deactivate this book? It won't appear in search.")) return;
    try {
      await apiFetch(`/library/books/${bookId}`, { method: "DELETE" });
      loadBooks(); loadStats();
    } catch (e) { err(e); }
  };

  const tabs = [
    { key: "books",   label: "Book Catalogue", show: true },
    { key: "issues",  label: "Issue Records",  show: isStaff },
    { key: "overdue", label: "Overdue",         show: isStaff },
    { key: "my",      label: "My Books",        show: !isAdmin },
  ].filter((t) => t.show);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Library</h1>
            <p className="mt-1 text-sm text-slate-500">Manage books, issue & return, fines</p>
          </div>
          {isAdmin && (
            <Button onClick={() => setShowAddBook(true)} className="flex items-center gap-2">
              <Plus size={16} /> Add Book
            </Button>
          )}
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertTriangle size={15} /> {error}
            <button onClick={() => setError("")} className="ml-auto"><X size={14} /></button>
          </div>
        )}

        {/* Stats */}
        {isStaff && stats && (
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
            <StatCard label="Total Books" value={stats.total_books} />
            <StatCard label="Total Copies" value={stats.total_copies} />
            <StatCard label="Available" value={stats.available_copies} accent="text-emerald-600" />
            <StatCard label="Issued" value={stats.issued_count} accent="text-blue-600" />
            <StatCard label="Overdue" value={stats.overdue_count} accent={stats.overdue_count > 0 ? "text-red-600" : "text-slate-900"} />
            <StatCard label="Fine Pending" value={`₹${stats.total_fine_pending}`} accent={stats.total_fine_pending > 0 ? "text-amber-600" : "text-slate-900"} />
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 border-b border-slate-200">
          {tabs.map((t) => (
            <button key={t.key} onClick={() => setTab(t.key as typeof tab)}
              className={`px-4 py-2 text-sm font-medium transition border-b-2 -mb-px ${
                tab === t.key ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-700"
              }`}>
              {t.label}
              {t.key === "overdue" && stats && stats.overdue_count > 0 && (
                <span className="ml-1.5 rounded-full bg-red-500 px-1.5 py-0.5 text-xs text-white">{stats.overdue_count}</span>
              )}
            </button>
          ))}
        </div>

        {/* ── BOOKS TAB ───────────────────────────────────────────────────── */}
        {tab === "books" && (
          <div className="space-y-4">
            {/* Filters */}
            <div className="flex flex-wrap gap-3">
              <div className="relative flex-1 min-w-45">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input placeholder="Search title, author, ISBN…" className="pl-9"
                  value={search} onChange={(e) => setSearch(e.target.value)} />
              </div>
              <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-400"
                value={catFilter} onChange={(e) => setCatFilter(e.target.value)}>
                <option value="">All categories</option>
                {categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm">
                <input type="checkbox" checked={availOnly} onChange={(e) => setAvailOnly(e.target.checked)} />
                Available only
              </label>
              <button onClick={loadBooks} className="flex items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50">
                <RefreshCw size={14} className={loadingBooks ? "animate-spin" : ""} />
              </button>
            </div>

            {loadingBooks ? (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-slate-400" /></div>
            ) : books.length === 0 ? (
              <Card><p className="py-8 text-center text-sm text-slate-400">No books found. {isAdmin && "Click \"Add Book\" to add one."}</p></Card>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {books.map((book) => (
                  <div key={book.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md transition flex flex-col gap-3">
                    <div className="flex items-start gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100">
                        <BookOpen size={20} className="text-slate-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-slate-900 leading-tight truncate">{book.title}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{book.author}</p>
                        {book.isbn && <p className="text-xs text-slate-400 font-mono">ISBN: {book.isbn}</p>}
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-1.5 text-xs">
                      {book.category && <span className="rounded-full bg-violet-100 px-2 py-0.5 text-violet-700 font-medium">{book.category}</span>}
                      {book.shelf_location && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">📍 {book.shelf_location}</span>}
                      {book.edition && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">{book.edition}</span>}
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="text-xs">
                        <span className={`font-semibold ${book.available_copies > 0 ? "text-emerald-600" : "text-red-500"}`}>
                          {book.available_copies}
                        </span>
                        <span className="text-slate-400"> / {book.total_copies} available</span>
                      </div>
                      <div className="flex gap-2">
                        {isStaff && book.available_copies > 0 && (
                          <button onClick={() => setShowIssueModal(book)}
                            className="flex items-center gap-1 rounded-lg bg-slate-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-slate-700">
                            <BookMarked size={12} /> Issue
                          </button>
                        )}
                        {isAdmin && (
                          <>
                            <button onClick={() => setShowEditBook(book)}
                              className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50">
                              Edit
                            </button>
                            <button onClick={() => handleDeactivate(book.id)}
                              className="rounded-lg border border-red-100 px-2 py-1 text-xs text-red-500 hover:bg-red-50">
                              <Trash2 size={12} />
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── ISSUES TAB ──────────────────────────────────────────────────── */}
        {tab === "issues" && isStaff && (
          <div className="space-y-4">
            <div className="flex gap-3">
              <select className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-400"
                value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="">All statuses</option>
                {["ISSUED","RETURNED","OVERDUE","LOST"].map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <button onClick={loadIssues} className="flex items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50">
                <RefreshCw size={14} className={loadingIssues ? "animate-spin" : ""} />
              </button>
            </div>
            <IssueTable
              issues={issues}
              loading={loadingIssues}
              expanded={expandedIssue}
              onExpand={setExpandedIssue}
              onReturn={(i) => setShowReturnModal(i)}
              onPayFine={handlePayFine}
              isStaff={isStaff}
            />
          </div>
        )}

        {/* ── OVERDUE TAB ─────────────────────────────────────────────────── */}
        {tab === "overdue" && isStaff && (
          <div className="space-y-4">
            {loadingOverdue ? (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-slate-400" /></div>
            ) : overdue.length === 0 ? (
              <Card>
                <div className="flex flex-col items-center gap-2 py-10">
                  <CheckCircle2 size={36} className="text-emerald-400" />
                  <p className="text-sm text-slate-500">No overdue books right now.</p>
                </div>
              </Card>
            ) : (
              <>
                <div className="flex items-center gap-2 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                  <ShieldAlert size={16} />
                  <strong>{overdue.length}</strong> book{overdue.length > 1 ? "s" : ""} overdue. Please follow up with borrowers.
                </div>
                <IssueTable
                  issues={overdue}
                  loading={false}
                  expanded={expandedIssue}
                  onExpand={setExpandedIssue}
                  onReturn={(i) => setShowReturnModal(i)}
                  onPayFine={handlePayFine}
                  isStaff={isStaff}
                />
              </>
            )}
          </div>
        )}

        {/* ── MY BOOKS TAB ────────────────────────────────────────────────── */}
        {tab === "my" && (
          <div className="space-y-4">
            {loadingMy ? (
              <div className="flex justify-center py-12"><Loader2 className="animate-spin text-slate-400" /></div>
            ) : myIssues.length === 0 ? (
              <Card><p className="py-8 text-center text-sm text-slate-400">You have no issued books.</p></Card>
            ) : (
              <div className="space-y-3">
                {myIssues.map((issue) => {
                  const meta = STATUS_META[issue.status] ?? STATUS_META["ISSUED"];
                  const fine = issue.fine_amount;
                  return (
                    <div key={issue.id} className={`rounded-2xl border p-4 ${issue.status === "OVERDUE" ? "border-red-200 bg-red-50" : "border-slate-200 bg-white"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-900">{issue.book_title}</p>
                          {issue.book_isbn && <p className="text-xs text-slate-400 font-mono">ISBN: {issue.book_isbn}</p>}
                          <p className="mt-1 text-xs text-slate-500">
                            Issued: {fmt(issue.issue_date)} &nbsp;·&nbsp; Due: {fmt(issue.due_date)}
                          </p>
                          {issue.status === "ISSUED" || issue.status === "OVERDUE" ? (
                            <p className={`mt-1 text-xs font-medium ${issue.days_overdue > 0 ? "text-red-600" : "text-slate-500"}`}>
                              {dueIn(issue.due_date)}
                            </p>
                          ) : issue.return_date ? (
                            <p className="mt-1 text-xs text-emerald-600">Returned: {fmt(issue.return_date)}</p>
                          ) : null}
                        </div>
                        <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${meta.color}`}>{meta.label}</span>
                      </div>
                      {fine > 0 && (
                        <div className={`mt-3 flex items-center gap-2 rounded-lg px-3 py-2 text-xs ${issue.fine_paid ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                          <IndianRupee size={12} />
                          Fine: ₹{fine} — {issue.fine_paid ? "Paid" : "Pending"}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── ADD BOOK MODAL ────────────────────────────────────────────────── */}
      {showAddBook && (
        <AddEditBookModal
          onClose={() => setShowAddBook(false)}
          onSaved={() => { setShowAddBook(false); loadBooks(); loadStats(); loadCategories(); }}
        />
      )}

      {/* ── EDIT BOOK MODAL ───────────────────────────────────────────────── */}
      {showEditBook && (
        <AddEditBookModal
          book={showEditBook}
          onClose={() => setShowEditBook(null)}
          onSaved={() => { setShowEditBook(null); loadBooks(); loadStats(); }}
        />
      )}

      {/* ── ISSUE MODAL ───────────────────────────────────────────────────── */}
      {showIssueModal && (
        <IssueBookModal
          book={showIssueModal}
          students={students}
          teachers={teachers}
          onClose={() => setShowIssueModal(null)}
          onSaved={() => { setShowIssueModal(null); loadBooks(); loadIssues(); loadStats(); }}
        />
      )}

      {/* ── RETURN MODAL ──────────────────────────────────────────────────── */}
      {showReturnModal && (
        <ReturnBookModal
          issue={showReturnModal}
          onClose={() => setShowReturnModal(null)}
          onSaved={() => { setShowReturnModal(null); loadBooks(); loadIssues(); loadOverdue(); loadStats(); }}
        />
      )}
    </AppShell>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// ISSUE TABLE COMPONENT
// ══════════════════════════════════════════════════════════════════════════════
function IssueTable({ issues, loading, expanded, onExpand, onReturn, onPayFine, isStaff }: {
  issues: Issue[]; loading: boolean; expanded: number | null;
  onExpand: (id: number | null) => void;
  onReturn: (issue: Issue) => void;
  onPayFine: (id: number) => void;
  isStaff: boolean;
}) {
  if (loading) return <div className="flex justify-center py-12"><Loader2 className="animate-spin text-slate-400" /></div>;
  if (issues.length === 0) return <Card><p className="py-8 text-center text-sm text-slate-400">No records found.</p></Card>;

  return (
    <Card className="overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              {["Book","Borrower","Issued","Due","Status","Fine","Actions"].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-medium text-slate-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {issues.map((issue) => {
              const meta = STATUS_META[issue.status] ?? STATUS_META["ISSUED"];
              const isExp = expanded === issue.id;
              return (
                <>
                  <tr key={issue.id} className="hover:bg-slate-50 transition cursor-pointer"
                    onClick={() => onExpand(isExp ? null : issue.id)}>
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-900 max-w-37.5 truncate">{issue.book_title}</p>
                      {issue.book_isbn && <p className="text-xs text-slate-400 font-mono">{issue.book_isbn}</p>}
                    </td>
                    <td className="px-4 py-3 text-slate-700">{issue.borrower_name}</td>
                    <td className="px-4 py-3 text-slate-500 text-xs">{fmt(issue.issue_date)}</td>
                    <td className={`px-4 py-3 text-xs font-medium ${issue.days_overdue > 0 && issue.status !== "RETURNED" ? "text-red-600" : "text-slate-500"}`}>
                      {fmt(issue.due_date)}
                      {issue.days_overdue > 0 && issue.status !== "RETURNED" && (
                        <span className="block text-red-500">+{issue.days_overdue}d</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${meta.color}`}>{meta.label}</span>
                    </td>
                    <td className="px-4 py-3">
                      {issue.fine_amount > 0 ? (
                        <span className={`text-xs font-medium ${issue.fine_paid ? "text-emerald-600" : "text-amber-600"}`}>
                          ₹{issue.fine_amount} {issue.fine_paid ? "✓" : ""}
                        </span>
                      ) : <span className="text-xs text-slate-400">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        {isStaff && issue.status !== "RETURNED" && issue.status !== "LOST" && (
                          <button onClick={(e) => { e.stopPropagation(); onReturn(issue); }}
                            className="flex items-center gap-1 rounded-lg bg-slate-900 px-2 py-1 text-xs font-medium text-white hover:bg-slate-700">
                            <RotateCcw size={11} /> Return
                          </button>
                        )}
                        {isStaff && issue.fine_amount > 0 && !issue.fine_paid && (
                          <button onClick={(e) => { e.stopPropagation(); onPayFine(issue.id); }}
                            className="flex items-center gap-1 rounded-lg border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100">
                            <IndianRupee size={11} /> Paid
                          </button>
                        )}
                        <span>{isExp ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}</span>
                      </div>
                    </td>
                  </tr>
                  {isExp && (
                    <tr key={`exp-${issue.id}`} className="bg-slate-50">
                      <td colSpan={7} className="px-6 py-3 text-xs text-slate-600">
                        <div className="flex flex-wrap gap-x-6 gap-y-1">
                          <span><b>Issue ID:</b> #{issue.id}</span>
                          {issue.return_date && <span><b>Returned:</b> {fmt(issue.return_date)}</span>}
                          <span><b>Fine/day:</b> ₹{issue.fine_per_day}</span>
                          {issue.notes && <span><b>Notes:</b> {issue.notes}</span>}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// ADD / EDIT BOOK MODAL
// ══════════════════════════════════════════════════════════════════════════════
function AddEditBookModal({ book, onClose, onSaved }: {
  book?: Book; onClose: () => void; onSaved: () => void;
}) {
  const isEdit = !!book;
  const [form, setForm] = useState({
    title: book?.title ?? "",
    author: book?.author ?? "",
    isbn: book?.isbn ?? "",
    publisher: book?.publisher ?? "",
    edition: book?.edition ?? "",
    category: book?.category ?? "",
    language: book?.language ?? "English",
    shelf_location: book?.shelf_location ?? "",
    description: book?.description ?? "",
    total_copies: String(book?.total_copies ?? 1),
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = (k: string, v: string) => setForm((p) => ({ ...p, [k]: v }));

  const handleSubmit = async () => {
    if (!form.title.trim() || !form.author.trim()) { setError("Title and author are required"); return; }
    setSaving(true); setError("");
    try {
      const body = { ...form, total_copies: Number(form.total_copies) };
      if (!body.isbn) delete (body as Record<string, unknown>).isbn;
      if (isEdit) {
        await apiFetch(`/library/books/${book!.id}`, { method: "PATCH", body: JSON.stringify(body) });
      } else {
        await apiFetch("/library/books", { method: "POST", body: JSON.stringify(body) });
      }
      onSaved();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally { setSaving(false); }
  };

  const fields: { label: string; key: string; placeholder?: string; type?: string }[] = [
    { label: "Title *", key: "title", placeholder: "e.g. Introduction to Physics" },
    { label: "Author *", key: "author", placeholder: "e.g. H.C. Verma" },
    { label: "ISBN", key: "isbn", placeholder: "e.g. 978-3-16-148410-0" },
    { label: "Publisher", key: "publisher", placeholder: "e.g. Pearson" },
    { label: "Edition", key: "edition", placeholder: "e.g. 5th Edition" },
    { label: "Category", key: "category", placeholder: "e.g. Science, History" },
    { label: "Language", key: "language", placeholder: "English" },
    { label: "Shelf Location", key: "shelf_location", placeholder: "e.g. A-12, Row 3" },
    { label: "Total Copies", key: "total_copies", type: "number", placeholder: "1" },
  ];

  return (
    <Modal title={isEdit ? "Edit Book" : "Add New Book"} onClose={onClose}>
      <div className="space-y-3 max-h-[65vh] overflow-y-auto pr-1">
        {fields.map((f) => (
          <div key={f.key}>
            <Label>{f.label}</Label>
            <Input type={f.type || "text"} placeholder={f.placeholder}
              value={(form as Record<string, string>)[f.key]}
              onChange={(e) => set(f.key, e.target.value)}
              min={f.type === "number" ? "1" : undefined} />
          </div>
        ))}
        <div>
          <Label>Description</Label>
          <textarea className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400 min-h-20"
            placeholder="Brief description of the book…"
            value={form.description}
            onChange={(e) => set("description", e.target.value)} />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
      <div className="mt-5 flex justify-end gap-3">
        <button onClick={onClose} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium hover:bg-slate-50">Cancel</button>
        <Button onClick={handleSubmit} disabled={saving}>
          {saving ? "Saving…" : isEdit ? "Save Changes" : "Add Book"}
        </Button>
      </div>
    </Modal>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// ISSUE BOOK MODAL
// ══════════════════════════════════════════════════════════════════════════════
function IssueBookModal({ book, students, teachers, onClose, onSaved }: {
  book: Book; students: Student[]; teachers: Teacher[];
  onClose: () => void; onSaved: () => void;
}) {
  const [borrowerType, setBorrowerType] = useState<"student" | "teacher">("student");
  const [borrowerId, setBorrowerId] = useState("");
  const [borrowerSearch, setBorrowerSearch] = useState("");
  const [issueDate, setIssueDate] = useState(today());
  const [dueDate, setDueDate] = useState("");
  const [finePerDay, setFinePerDay] = useState("1");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const filteredStudents = students.filter((s) =>
    `${s.first_name} ${s.last_name ?? ""} ${s.admission_no}`.toLowerCase().includes(borrowerSearch.toLowerCase())
  );
  const filteredTeachers = teachers.filter((t) =>
    `${t.full_name} ${t.employee_id}`.toLowerCase().includes(borrowerSearch.toLowerCase())
  );

  const handleSubmit = async () => {
    if (!borrowerId) { setError("Select a borrower"); return; }
    if (!dueDate)     { setError("Due date is required"); return; }
    if (dueDate <= issueDate) { setError("Due date must be after issue date"); return; }
    setSaving(true); setError("");
    try {
      await apiFetch("/library/issues", {
        method: "POST",
        body: JSON.stringify({
          book_id: book.id,
          student_id: borrowerType === "student" ? Number(borrowerId) : null,
          teacher_id: borrowerType === "teacher" ? Number(borrowerId) : null,
          issue_date: issueDate,
          due_date: dueDate,
          fine_per_day: Number(finePerDay),
          notes: notes || null,
        }),
      });
      onSaved();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to issue");
    } finally { setSaving(false); }
  };

  return (
    <Modal title={`Issue Book — ${book.title}`} onClose={onClose}>
      <div className="space-y-4">
        <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm">
          <p className="font-medium text-slate-800">{book.title}</p>
          <p className="text-slate-500">{book.author} · {book.available_copies} copies available</p>
        </div>

        <div>
          <Label>Borrow for</Label>
          <div className="flex gap-2">
            {(["student","teacher"] as const).map((t) => (
              <button key={t} onClick={() => { setBorrowerType(t); setBorrowerId(""); setBorrowerSearch(""); }}
                className={`flex-1 rounded-xl border py-2 text-sm font-medium capitalize transition ${
                  borrowerType === t ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 text-slate-600 hover:bg-slate-50"
                }`}>
                {t}
              </button>
            ))}
          </div>
        </div>

        <div>
          <Label>Search {borrowerType}</Label>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input className="pl-8" placeholder={`Search by name or ID…`}
              value={borrowerSearch} onChange={(e) => { setBorrowerSearch(e.target.value); setBorrowerId(""); }} />
          </div>
          {borrowerSearch && (
            <div className="mt-1 max-h-40 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-md">
              {(borrowerType === "student" ? filteredStudents : filteredTeachers).slice(0, 10).map((p) => {
                const id = String(p.id);
                const label = borrowerType === "student"
                  ? `${(p as Student).first_name} ${(p as Student).last_name ?? ""} (${(p as Student).admission_no})`
                  : `${(p as Teacher).full_name} (${(p as Teacher).employee_id})`;
                return (
                  <button key={id} onClick={() => { setBorrowerId(id); setBorrowerSearch(label.trim()); }}
                    className="w-full px-4 py-2 text-left text-sm hover:bg-slate-50">
                    {label}
                  </button>
                );
              })}
              {(borrowerType === "student" ? filteredStudents : filteredTeachers).length === 0 && (
                <p className="px-4 py-3 text-sm text-slate-400">No results</p>
              )}
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div><Label>Issue date</Label><Input type="date" value={issueDate} onChange={(e) => setIssueDate(e.target.value)} /></div>
          <div><Label>Due date *</Label><Input type="date" value={dueDate} min={issueDate} onChange={(e) => setDueDate(e.target.value)} /></div>
        </div>

        <div>
          <Label>Fine per day (₹)</Label>
          <Input type="number" min="0" value={finePerDay} onChange={(e) => setFinePerDay(e.target.value)} />
        </div>
        <div>
          <Label>Notes (optional)</Label>
          <Input placeholder="Any remarks…" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
      <div className="mt-5 flex justify-end gap-3">
        <button onClick={onClose} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium hover:bg-slate-50">Cancel</button>
        <Button onClick={handleSubmit} disabled={saving || !borrowerId}>
          {saving ? "Issuing…" : "Issue Book"}
        </Button>
      </div>
    </Modal>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// RETURN BOOK MODAL
// ══════════════════════════════════════════════════════════════════════════════
function ReturnBookModal({ issue, onClose, onSaved }: {
  issue: Issue; onClose: () => void; onSaved: () => void;
}) {
  const [returnDate, setReturnDate] = useState(today());
  const [markLost, setMarkLost] = useState(false);
  const [fineOverride, setFineOverride] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const calcFine = () => {
    if (returnDate > issue.due_date) {
      return Math.max(0, Math.ceil((new Date(returnDate).getTime() - new Date(issue.due_date).getTime()) / 86400000)) * issue.fine_per_day;
    }
    return 0;
  };
  const previewFine = fineOverride !== "" ? Number(fineOverride) : calcFine();

  const handleSubmit = async () => {
    setSaving(true); setError("");
    try {
      await apiFetch(`/library/issues/${issue.id}/return`, {
        method: "POST",
        body: JSON.stringify({
          return_date: returnDate,
          mark_lost: markLost,
          fine_override: fineOverride !== "" ? Number(fineOverride) : null,
          notes: notes || null,
        }),
      });
      onSaved();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Return failed");
    } finally { setSaving(false); }
  };

  return (
    <Modal title="Return Book" onClose={onClose}>
      <div className="space-y-4">
        <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm">
          <p className="font-medium text-slate-800">{issue.book_title}</p>
          <p className="text-slate-500">Borrower: <b>{issue.borrower_name}</b></p>
          <p className="text-slate-500">Issued: {fmt(issue.issue_date)} · Due: {fmt(issue.due_date)}</p>
        </div>

        <div><Label>Return date</Label>
          <Input type="date" value={returnDate} onChange={(e) => setReturnDate(e.target.value)} />
        </div>

        <div className="rounded-xl border border-amber-100 bg-amber-50 px-4 py-3">
          <p className="text-sm font-medium text-amber-800">Fine Calculation</p>
          <p className="mt-1 text-sm text-amber-700">
            ₹{issue.fine_per_day}/day × {Math.max(0, Math.ceil((new Date(returnDate).getTime() - new Date(issue.due_date).getTime()) / 86400000))} overdue days = <b>₹{calcFine()}</b>
          </p>
        </div>

        <div>
          <Label>Override fine amount (₹)</Label>
          <Input type="number" min="0" placeholder={`Auto: ₹${calcFine()}`}
            value={fineOverride} onChange={(e) => setFineOverride(e.target.value)} />
          <p className="mt-1 text-xs text-slate-400">Leave blank to use auto-calculated fine. Final: ₹{previewFine}</p>
        </div>

        <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
          <input type="checkbox" checked={markLost} onChange={(e) => setMarkLost(e.target.checked)} />
          <span>Mark as <b>Lost</b> (copy won't be restored to stock)</span>
        </label>

        <div><Label>Notes</Label>
          <Input placeholder="Condition on return, remarks…" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
      <div className="mt-5 flex justify-end gap-3">
        <button onClick={onClose} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium hover:bg-slate-50">Cancel</button>
        <Button onClick={handleSubmit} disabled={saving}>
          {saving ? "Processing…" : markLost ? "Mark as Lost" : "Confirm Return"}
        </Button>
      </div>
    </Modal>
  );
}
