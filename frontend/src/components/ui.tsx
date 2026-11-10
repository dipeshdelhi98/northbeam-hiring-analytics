"use client";

import { ArrowDownRight, ArrowUpRight, Minus, X } from "lucide-react";
import { useEffect } from "react";
import type { Role } from "@/lib/api";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <section className={cx("card", className)}>{children}</section>;
}

export function CardHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5">
      <div>
        <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
        {subtitle && <p className="mt-0.5 text-[13px] text-ink-3">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <div className="mt-1 text-sm text-ink-3">{subtitle}</div>}
      </div>
      {right}
    </div>
  );
}

/** A headline number. `value` is the API's display string, rendered verbatim. */
export function StatTile({
  label, value, hint, icon, delta,
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: React.ReactNode;
  delta?: { text: string; direction: "up" | "down" | "flat" | null; favourable: boolean | null };
}) {
  return (
    <div className="card flex flex-col gap-2 p-5">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-ink-2">{label}</span>
        {icon && <span className="grid size-8 place-items-center rounded-lg bg-accent-soft text-accent">{icon}</span>}
      </div>
      <div className="tabular text-[28px] font-semibold leading-tight tracking-tight text-ink">{value}</div>
      {delta && <Delta {...delta} />}
      {hint && <div className="text-xs text-ink-3">{hint}</div>}
    </div>
  );
}

export function Delta({ text, direction, favourable }: { text: string; direction: "up" | "down" | "flat" | null; favourable: boolean | null }) {
  const Icon = direction === "up" ? ArrowUpRight : direction === "down" ? ArrowDownRight : Minus;
  const tone = favourable === true ? "bg-good-soft text-good" : favourable === false ? "bg-bad-soft text-bad" : "bg-surface-2 text-ink-2";
  return (
    <span className={cx("inline-flex w-fit items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", tone)}>
      <Icon size={13} aria-hidden />
      <span className="sr-only">{favourable === true ? "Improved" : favourable === false ? "Worsened" : "Changed"}:</span>
      {text}
    </span>
  );
}

const ROLE_LABEL: Record<Role, string> = { admin: "Admin", recruiter: "Recruiter", hiring_manager: "Hiring manager" };

export function RoleBadge({ role }: { role: Role }) {
  const tone = role === "admin" ? "bg-warn-soft text-warn" : role === "recruiter" ? "bg-accent-soft text-accent" : "bg-good-soft text-good";
  return <span className={cx("inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold", tone)}>{ROLE_LABEL[role] ?? role}</span>;
}

/** Stage identity = dot colour + text label (never colour alone). */
export function StageBadge({ stage }: { stage: string | null }) {
  if (!stage) return <span className="text-ink-3">–</span>;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line px-2 py-0.5 text-xs font-medium text-ink-2">
      <span className="size-2 rounded-full" style={{ background: `var(--stage-${stage.toLowerCase()})` }} aria-hidden />
      {stage}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  const open = status === "open";
  return (
    <span className={cx("inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize", open ? "bg-good-soft text-good" : "bg-surface-2 text-ink-3")}>
      {status}
    </span>
  );
}

export function Avatar({ name, size = 32 }: { name: string; size?: number }) {
  const initials = name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return (
    <span
      className="grid shrink-0 place-items-center rounded-full bg-accent-soft font-semibold text-accent"
      style={{ width: size, height: size, fontSize: size * 0.38 }}
      aria-hidden
    >
      {initials}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton", className)} />;
}

export function ErrorNote({ message }: { message: string }) {
  return <div className="rounded-lg border border-bad/30 bg-bad-soft px-4 py-3 text-sm text-bad">{message}</div>;
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="px-5 py-12 text-center">
      <div className="text-sm font-medium text-ink-2">{title}</div>
      {hint && <div className="mt-1 text-xs text-ink-3">{hint}</div>}
    </div>
  );
}

export function Drawer({ open, onClose, title, subtitle, children }: {
  open: boolean; onClose: () => void; title: React.ReactNode; subtitle?: React.ReactNode; children: React.ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true">
      <button className="absolute inset-0 bg-black/30 backdrop-blur-[1px]" aria-label="Close" onClick={onClose} />
      <div className="drawer-enter relative flex h-full w-full max-w-xl flex-col border-l border-line bg-surface shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-5">
          <div className="min-w-0">
            <div className="text-lg font-semibold text-ink">{title}</div>
            {subtitle && <div className="mt-1 text-sm text-ink-3">{subtitle}</div>}
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink" aria-label="Close panel">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

export const th = "px-4 py-2.5 text-left text-[12px] font-medium text-ink-3 whitespace-nowrap";
export const thNum = th + " text-right";
export const td = "px-4 py-3 text-sm text-ink-2 whitespace-nowrap";
export const tdNum = td + " text-right tabular text-ink";
