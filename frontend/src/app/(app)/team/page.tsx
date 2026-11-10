"use client";

import { useState } from "react";
import { Briefcase, Clock, Percent, Trophy } from "lucide-react";
import { useAuth } from "@/components/auth";
import { TeamHiresChart } from "@/components/charts";
import {
  Avatar, Card, CardHeader, cx, Empty, ErrorNote, PageHeader, RoleBadge, Skeleton, td, tdNum, th, thNum,
} from "@/components/ui";
import type { Role, TeamRow } from "@/lib/api";
import { useApi } from "@/lib/useApi";

const FILTERS: { key: "all" | Role; label: string }[] = [
  { key: "all", label: "Everyone" },
  { key: "recruiter", label: "Recruiters" },
  { key: "hiring_manager", label: "Hiring managers" },
  { key: "admin", label: "Admins" },
];

function PersonCard({ p }: { p: TeamRow }) {
  return (
    <div className="card flex flex-col gap-4 p-5">
      <div className="flex items-center gap-3">
        <Avatar name={p.name} size={42} />
        <div className="min-w-0">
          <div className="truncate font-semibold text-ink">{p.name}</div>
          <div className="mt-0.5 flex items-center gap-2"><RoleBadge role={p.role} />{p.department && <span className="text-xs text-ink-3">{p.department}</span>}</div>
        </div>
      </div>
      {p.requisitions ? (
        <dl className="grid grid-cols-2 gap-3 text-sm">
          {[
            [<Briefcase key="i" size={13} />, "Requisitions", String(p.requisitions)],
            [<Trophy key="i" size={13} />, "Hires", String(p.hires)],
            [<Clock key="i" size={13} />, "Median time to hire", p.median_days_display],
            [<Percent key="i" size={13} />, "Offer acceptance", p.acceptance_display],
          ].map(([icon, k, v]) => (
            <div key={k as string} className="rounded-lg bg-surface-2 px-3 py-2">
              <dt className="flex items-center gap-1 text-xs text-ink-3">{icon}{k}</dt>
              <dd className="tabular mt-0.5 font-semibold text-ink">{v}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <div className="rounded-lg bg-surface-2 px-3 py-3 text-xs text-ink-3">No requisitions owned. {p.role === "admin" ? "Admins see all data." : ""}</div>
      )}
    </div>
  );
}

export default function TeamPage() {
  const { me } = useAuth();
  const { data, error } = useApi<TeamRow[]>("/api/team");
  const [filter, setFilter] = useState<"all" | Role>("all");
  const [view, setView] = useState<"cards" | "table">("cards");
  const rows = (data ?? []).filter((r) => filter === "all" || r.role === filter);

  return (
    <>
      <PageHeader
        title="Team"
        subtitle={me?.role === "admin" ? "Everyone with access, and the results on the requisitions they own." : "You and the colleagues who share your requisitions. Figures cover your requisitions only."}
      />
      {error && <ErrorNote message={error} />}

      <Card className="mb-6">
        <CardHeader title="Hires by owner" subtitle="All-time hires on the requisitions each person owns. A recruiter and a hiring manager share credit for the same hire." />
        <div className="p-4 pt-2">
          {data ? (data.some((r) => r.requisitions) ? <TeamHiresChart rows={data} /> : <Empty title="No owned requisitions" />) : <Skeleton className="h-64" />}
        </div>
      </Card>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.filter((f) => f.key === "all" || (data ?? []).some((r) => r.role === f.key)).map((f) => (
            <button key={f.key} onClick={() => setFilter(f.key)}
              className={cx("rounded-full border px-3 py-1.5 text-xs font-medium transition", filter === f.key ? "border-accent bg-accent-soft text-accent" : "border-line bg-surface text-ink-2 hover:bg-surface-2")}>
              {f.label}
            </button>
          ))}
        </div>
        <div className="flex rounded-lg border border-line bg-surface p-0.5 text-xs font-medium">
          {(["cards", "table"] as const).map((v) => (
            <button key={v} onClick={() => setView(v)} className={cx("rounded-md px-3 py-1.5 capitalize", view === v ? "bg-surface-2 text-ink" : "text-ink-3")}>{v}</button>
          ))}
        </div>
      </div>

      {!data && <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-48" />)}</div>}

      {data && view === "cards" && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">{rows.map((p) => <PersonCard key={p.user_id} p={p} />)}</div>
      )}

      {data && view === "table" && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-line bg-surface-2">
                <tr>
                  <th className={th}>Person</th><th className={th}>Role</th><th className={thNum}>Requisitions</th><th className={thNum}>Applications</th>
                  <th className={thNum}>In progress</th><th className={thNum}>Hires</th><th className={thNum}>Median time to hire</th><th className={thNum}>Offer acceptance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((p) => (
                  <tr key={p.user_id}>
                    <td className={td}><div className="flex items-center gap-2.5"><Avatar name={p.name} size={28} /><span className="font-medium text-ink">{p.name}</span></div></td>
                    <td className={td}><RoleBadge role={p.role} /></td>
                    <td className={tdNum}>{p.requisitions}</td>
                    <td className={tdNum}>{p.applications}</td>
                    <td className={tdNum}>{p.in_progress}</td>
                    <td className={tdNum}>{p.hires}</td>
                    <td className={tdNum}>{p.median_days_display}</td>
                    <td className={tdNum}>{p.acceptance_display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {data && !rows.length && <Empty title="Nobody in this group" />}
    </>
  );
}
