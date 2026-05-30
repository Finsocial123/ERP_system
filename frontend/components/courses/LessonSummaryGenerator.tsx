"use client";

import { useState } from "react";
import { BookMarked, Loader2, AlertCircle, CheckCircle, FileText, Volume2, Eye } from "lucide-react";
import { generateLessonSummary } from "@/lib/summaryApi";
import type { LMSLesson } from "@/types";
import { API_BASE } from "@/lib/api";

type Props = {
  lesson: LMSLesson;
  courseTitle?: string;
  /** When true the component renders fully expanded without a trigger button */
  embedded?: boolean;
};

type SummaryState = "idle" | "generating" | "completed" | "error";
interface SummaryContent {
  title: string;
  overview: string;
  key_concepts: string[];
  key_takeaway: string;
}

export default function LessonSummaryGenerator({ lesson, courseTitle, embedded = false }: Props) {
  const [open, setOpen] = useState(embedded);
  const [state, setState] = useState<SummaryState>("idle");
  const [summary, setSummary] = useState<SummaryContent | null>(null);
  const [error, setError] = useState("");
  const [selectedSource, setSelectedSource] = useState<"transcript" | "notes" | "visual">("transcript");

  const availableSources = [
    { id: "transcript", label: "Video Transcript", icon: Volume2, available: !!lesson.video_url },
    { id: "notes", label: "PDF Notes", icon: FileText, available: !!lesson.pdf_url },
    { id: "visual", label: "Visual Content", icon: Eye, available: !!lesson.video_url },
  ];

  const handleGenerateSummary = async () => {
    setState("generating"); setError("");
    try {
      const res = await fetch(
        `${API_BASE}/lessons/${lesson.id}/course/${lesson.course_id}/${selectedSource}/summary`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ course_id: lesson.course_id, lesson_id: lesson.id, source: selectedSource }),
        },
      );
      if (!res.ok) throw new Error("Failed to generate summary");
      const data = await res.json();
      setSummary({ overview: data.overview, title: data.lesson_title, key_concepts: data.key_concepts, key_takeaway: data.key_takeaway });
      setState("completed");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate summary");
      setState("error");
    }
  };

  const handleReset = () => { setState("idle"); setSummary(null); setError(""); };
  const handleClose = () => { handleReset(); if (!embedded) setOpen(false); };

  if (!embedded && !open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{ display: "flex", alignItems: "center", gap: 6, padding: "7px 14px", borderRadius: 9, background: "#fffbeb", color: "#b45309", border: "none", cursor: "pointer", fontSize: "0.8rem", fontWeight: 600, transition: "background 0.13s" }}
        onMouseEnter={(e) => ((e.target as HTMLElement).style.background = "#fef3c7")}
        onMouseLeave={(e) => ((e.target as HTMLElement).style.background = "#fffbeb")}
      >
        <BookMarked size={15} /> Summary
      </button>
    );
  }

  if (!embedded && open) {
    return (
      <div style={{ position: "fixed", inset: 0, zIndex: 50, background: "rgba(15,23,42,0.55)", display: "flex", alignItems: "center", justifyContent: "center", padding: 16, overflowY: "auto" }}>
        <div style={{ background: "white", borderRadius: 16, boxShadow: "0 24px 64px rgba(0,0,0,0.18)", width: "100%", maxWidth: 560, maxHeight: "90vh", overflowY: "auto" }}>
          <div style={{ background: "linear-gradient(135deg,#d97706,#b45309)", padding: "20px 24px", borderRadius: "16px 16px 0 0", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <BookMarked size={20} color="white" />
              <div>
                <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "white", margin: 0 }}>Lesson Summary</h2>
                <p style={{ fontSize: "0.72rem", color: "#fde68a", margin: 0 }}>{lesson.title}</p>
              </div>
            </div>
            <button onClick={handleClose} style={{ background: "rgba(255,255,255,0.15)", border: "none", borderRadius: 8, padding: "4px 8px", color: "white", cursor: "pointer", fontSize: "0.8rem" }}>✕</button>
          </div>
          <div style={{ padding: 24 }}>
            <SummaryContent state={state} summary={summary} error={error} availableSources={availableSources} selectedSource={selectedSource} setSelectedSource={setSelectedSource as (v: string) => void} onGenerate={handleGenerateSummary} onReset={handleReset} onClose={handleClose} />
          </div>
        </div>
      </div>
    );
  }

  // Embedded
  return (
    <div style={{ flex: 1, minHeight: 0, overflowY: "auto", scrollbarWidth: "thin", scrollbarColor: "#cbd5e1 transparent" }}>
      <SummaryContent state={state} summary={summary} error={error} availableSources={availableSources} selectedSource={selectedSource} setSelectedSource={setSelectedSource as (v: string) => void} onGenerate={handleGenerateSummary} onReset={handleReset} onClose={handleClose} embedded />
    </div>
  );
}

type SourceItem = { id: string; label: string; icon: React.ComponentType<{ size?: number }>; available: boolean };
type SummaryContentProps = {
  state: SummaryState; summary: SummaryContent | null; error: string;
  availableSources: SourceItem[]; selectedSource: string;
  setSelectedSource: (v: string) => void;
  onGenerate: () => void; onReset: () => void; onClose: () => void;
  embedded?: boolean;
};

function SummaryContent({ state, summary, error, availableSources, selectedSource, setSelectedSource, onGenerate, onReset, onClose, embedded }: SummaryContentProps) {
  const btnBase: React.CSSProperties = { border: "none", borderRadius: 9, padding: "8px 16px", fontSize: "0.8rem", fontWeight: 600, cursor: "pointer", transition: "background 0.13s" };

  if (state === "idle") return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <p style={{ fontSize: "0.72rem", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", margin: 0 }}>Select Source</p>
      {availableSources.map((src) => {
        const Icon = src.icon;
        return (
          <button key={src.id} onClick={() => src.available && setSelectedSource(src.id)} disabled={!src.available}
            style={{ ...btnBase, display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", background: selectedSource === src.id ? "#fffbeb" : "#f8fafc", border: `2px solid ${selectedSource === src.id ? "#d97706" : "#e2e8f0"}`, color: src.available ? "#374151" : "#94a3b8", opacity: src.available ? 1 : 0.5, cursor: src.available ? "pointer" : "not-allowed", textAlign: "left" }}>
            <Icon size={16} />
            <span style={{ flex: 1, fontWeight: 600, fontSize: "0.8rem" }}>{src.label}</span>
            {!src.available && <span style={{ fontSize: "0.7rem", color: "#94a3b8" }}>Not available</span>}
          </button>
        );
      })}
      <button onClick={onGenerate} disabled={!availableSources.find((s) => s.id === selectedSource && s.available)}
        style={{ ...btnBase, background: "#d97706", color: "white", padding: 10 }}>
        Generate Summary
      </button>
    </div>
  );

  if (state === "generating") return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "32px 0", gap: 10 }}>
      <Loader2 size={28} color="#d97706" className="animate-spin" />
      <p style={{ fontSize: "0.85rem", color: "#64748b", margin: 0 }}>Generating summary…</p>
    </div>
  );

  if (state === "completed" && summary) return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 12px", background: "#f0fdf4", borderRadius: 8, border: "1px solid #bbf7d0" }}>
        <CheckCircle size={14} color="#10b981" />
        <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#065f46" }}>Summary generated successfully</span>
      </div>
      <div style={{ background: "linear-gradient(135deg,#fffbeb,#fef3c7)", borderRadius: 12, border: "1px solid #fde68a", padding: "14px 16px" }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "#0f172a", margin: "0 0 2px" }}>{summary.title}</h2>
        <p style={{ fontSize: "0.7rem", color: "#92400e", margin: 0 }}>AI-generated lesson summary</p>
      </div>
      <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: 12, padding: "12px 14px" }}>
        <p style={{ fontSize: "0.72rem", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 6px" }}>📘 Overview</p>
        <p style={{ fontSize: "0.8rem", color: "#374151", lineHeight: 1.65, margin: 0 }}>{summary.overview}</p>
      </div>
      {summary.key_concepts?.length > 0 && (
        <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: 12, padding: "12px 14px" }}>
          <p style={{ fontSize: "0.72rem", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 8px" }}>🧠 Topics Covered</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {summary.key_concepts.map((concept, i) => (
              <span key={i} style={{ padding: "4px 10px", background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 100, fontSize: "0.72rem", fontWeight: 500, color: "#78350f" }}>
                {concept}
              </span>
            ))}
          </div>
        </div>
      )}
      <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 12, padding: "12px 14px" }}>
        <p style={{ fontSize: "0.72rem", fontWeight: 700, color: "#1d4ed8", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 6px" }}>🎯 Key Takeaway</p>
        <p style={{ fontSize: "0.8rem", color: "#1e40af", lineHeight: 1.6, fontWeight: 500, margin: 0 }}>{summary.key_takeaway}</p>
      </div>
      <button onClick={onReset} style={{ ...btnBase, background: "#d97706", color: "white", padding: 10 }}>
        Generate Another
      </button>
    </div>
  );

  if (state === "error") return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ padding: "12px 14px", background: "#fef2f2", borderRadius: 10, border: "1px solid #fecaca", display: "flex", gap: 8 }}>
        <AlertCircle size={16} color="#ef4444" style={{ flexShrink: 0, marginTop: 1 }} />
        <p style={{ fontSize: "0.78rem", color: "#991b1b", margin: 0 }}>{error}</p>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={onReset} style={{ ...btnBase, flex: 1, background: "#d97706", color: "white" }}>Try Again</button>
        <button onClick={onClose} style={{ ...btnBase, flex: 1, background: "#f1f5f9", color: "#475569" }}>Close</button>
      </div>
    </div>
  );

  return null;
}
