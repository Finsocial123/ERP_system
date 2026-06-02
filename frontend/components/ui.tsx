import Link from "next/link";
import type { ReactNode } from "react";

export function Button({ children, className = "", style, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`rounded-xl px-4 py-2 text-sm font-semibold text-white shadow-sm transition disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
      style={{ background: "var(--erp-primary, #0f172a)", borderRadius: "var(--erp-border-radius, 16px)", ...style }}
      {...props}
    >
      {children}
    </button>
  );
}

export function Input({ className = "", style, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none transition focus:border-slate-400 ${className}`}
      style={{ borderRadius: "var(--erp-border-radius, 16px)", ...style }}
      {...props}
    />
  );
}

export function Textarea({ className = "", style, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={`min-h-24 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm outline-none transition focus:border-slate-400 ${className}`}
      style={{ borderRadius: "var(--erp-border-radius, 16px)", ...style }}
      {...props}
    />
  );
}

export function Label({ children }: { children: ReactNode }) {
  return <label className="mb-1 block text-sm font-medium text-slate-700">{children}</label>;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm ${className}`} style={{ borderRadius: "var(--erp-border-radius, 16px)" }}>{children}</div>;
}

export function AuthLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="font-semibold underline underline-offset-4" style={{ color: "var(--erp-primary, #0f172a)" }}>
      {children}
    </Link>
  );
}
