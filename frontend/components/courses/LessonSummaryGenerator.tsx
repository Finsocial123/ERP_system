"use client";

import { useState, useEffect } from "react";
import { BookMarked, Loader2, AlertCircle, CheckCircle } from "lucide-react";
import type { LMSLesson } from "@/types";
import { apiFetch } from "@/lib/api";

type Props = {
  lesson: LMSLesson;
  embedded?: boolean;
};

type SummaryState = "idle" | "loading" | "completed" | "error";

interface SummaryContent {
  lesson_title: string;
  overview: string;
  key_concepts: string[];
  key_takeaway: string;
}

export default function LessonSummaryGenerator({
  lesson,
  embedded = false,
}: Props) {
  const [open, setOpen] = useState(embedded);
  const [state, setState] = useState<SummaryState>("idle");
  const [summary, setSummary] = useState<SummaryContent | null>(null);
  const [error, setError] = useState("");

  const fetchSummary = async () => {
    setState("loading");
    setError("");
    try {
      const data = await apiFetch<SummaryContent>(`/lessons/${lesson.id}/summary`);
      setSummary(data);
      setState("completed");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch summary");
      setState("error");
    }
  };

  // Fetch immediately when opened
  useEffect(() => {
    if (open && state === "idle") {
      fetchSummary();
    }
  }, [open]);

  const handleClose = () => {
    if (!embedded) setOpen(false);
  };

  if (!embedded && !open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "7px 14px",
          borderRadius: 9,
          background: "#fffbeb",
          color: "#b45309",
          border: "none",
          cursor: "pointer",
          fontSize: "0.8rem",
          fontWeight: 600,
        }}
      >
        <BookMarked size={15} /> Summary
      </button>
    );
  }

  const content = (
    <SummaryBody
      state={state}
      summary={summary}
      error={error}
      onRetry={fetchSummary}
      onClose={handleClose}
    />
  );

  if (embedded) {
    return (
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          scrollbarWidth: "thin",
          scrollbarColor: "#cbd5e1 transparent",
        }}
      >
        {content}
      </div>
    );
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        background: "rgba(15,23,42,0.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        overflowY: "auto",
      }}
    >
      <div
        style={{
          background: "white",
          borderRadius: 16,
          boxShadow: "0 24px 64px rgba(0,0,0,0.18)",
          width: "100%",
          maxWidth: 560,
          maxHeight: "90vh",
          overflowY: "auto",
        }}
      >
        {/* Header */}
        <div
          style={{
            background: "linear-gradient(135deg,#d97706,#b45309)",
            padding: "20px 24px",
            borderRadius: "16px 16px 0 0",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <BookMarked size={20} color="white" />
            <div>
              <h2
                style={{
                  fontSize: "1rem",
                  fontWeight: 700,
                  color: "white",
                  margin: 0,
                }}
              >
                Lesson Summary
              </h2>
              <p style={{ fontSize: "0.72rem", color: "#fde68a", margin: 0 }}>
                {lesson.title}
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            style={{
              background: "rgba(255,255,255,0.15)",
              border: "none",
              borderRadius: 8,
              padding: "4px 8px",
              color: "white",
              cursor: "pointer",
              fontSize: "0.8rem",
            }}
          >
            ✕
          </button>
        </div>

        <div style={{ padding: 24 }}>{content}</div>
      </div>
    </div>
  );
}

// ── Body ──────────────────────────────────────────────────────────────────────

type BodyProps = {
  state: SummaryState;
  summary: SummaryContent | null;
  error: string;
  onRetry: () => void;
  onClose: () => void;
};

function SummaryBody({ state, summary, error, onRetry, onClose }: BodyProps) {
  const btnBase: React.CSSProperties = {
    border: "none",
    borderRadius: 9,
    padding: "8px 16px",
    fontSize: "0.8rem",
    fontWeight: 600,
    cursor: "pointer",
  };

  if (state === "loading")
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          padding: "48px 0",
          gap: 10,
        }}
      >
        <Loader2 size={28} color="#d97706" className="animate-spin" />
        <p style={{ fontSize: "0.85rem", color: "#64748b", margin: 0 }}>
          Loading summary…
        </p>
      </div>
    );

  if (state === "error")
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div
          style={{
            padding: "12px 14px",
            background: "#fef2f2",
            borderRadius: 10,
            border: "1px solid #fecaca",
            display: "flex",
            gap: 8,
          }}
        >
          <AlertCircle
            size={16}
            color="#ef4444"
            style={{ flexShrink: 0, marginTop: 1 }}
          />
          <p style={{ fontSize: "0.78rem", color: "#991b1b", margin: 0 }}>
            {error}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={onRetry}
            style={{
              ...btnBase,
              flex: 1,
              background: "#d97706",
              color: "white",
            }}
          >
            Try Again
          </button>
          <button
            onClick={onClose}
            style={{
              ...btnBase,
              flex: 1,
              background: "#f1f5f9",
              color: "#475569",
            }}
          >
            Close
          </button>
        </div>
      </div>
    );

  if (state === "completed" && summary)
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "8px 12px",
            background: "#f0fdf4",
            borderRadius: 8,
            border: "1px solid #bbf7d0",
          }}
        >
          <CheckCircle size={14} color="#10b981" />
          <span
            style={{ fontSize: "0.75rem", fontWeight: 600, color: "#065f46" }}
          >
            AI-generated summary
          </span>
        </div>

        {/* Title */}
        <div
          style={{
            background: "linear-gradient(135deg,#fffbeb,#fef3c7)",
            borderRadius: 12,
            border: "1px solid #fde68a",
            padding: "14px 16px",
          }}
        >
          <h2
            style={{
              fontSize: "1rem",
              fontWeight: 700,
              color: "#0f172a",
              margin: 0,
            }}
          >
            {summary.lesson_title}
          </h2>
        </div>

        {/* Overview */}
        <div
          style={{
            background: "white",
            border: "1px solid #e2e8f0",
            borderRadius: 12,
            padding: "12px 14px",
          }}
        >
          <p
            style={{
              fontSize: "0.72rem",
              fontWeight: 700,
              color: "#64748b",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              margin: "0 0 6px",
            }}
          >
            📘 Overview
          </p>
          <p
            style={{
              fontSize: "0.8rem",
              color: "#374151",
              lineHeight: 1.65,
              margin: 0,
            }}
          >
            {summary.overview}
          </p>
        </div>

        {/* Key Concepts */}
        {summary.key_concepts?.length > 0 && (
          <div
            style={{
              background: "white",
              border: "1px solid #e2e8f0",
              borderRadius: 12,
              padding: "12px 14px",
            }}
          >
            <p
              style={{
                fontSize: "0.72rem",
                fontWeight: 700,
                color: "#64748b",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                margin: "0 0 8px",
              }}
            >
              🧠 Topics Covered
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {summary.key_concepts.map((concept, i) => (
                <span
                  key={i}
                  style={{
                    padding: "4px 10px",
                    background: "#fffbeb",
                    border: "1px solid #fde68a",
                    borderRadius: 100,
                    fontSize: "0.72rem",
                    fontWeight: 500,
                    color: "#78350f",
                  }}
                >
                  {concept}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Key Takeaway */}
        <div
          style={{
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            borderRadius: 12,
            padding: "12px 14px",
          }}
        >
          <p
            style={{
              fontSize: "0.72rem",
              fontWeight: 700,
              color: "#1d4ed8",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              margin: "0 0 6px",
            }}
          >
            🎯 Key Takeaway
          </p>
          <p
            style={{
              fontSize: "0.8rem",
              color: "#1e40af",
              lineHeight: 1.6,
              fontWeight: 500,
              margin: 0,
            }}
          >
            {summary.key_takeaway}
          </p>
        </div>
      </div>
    );

  return null;
}
