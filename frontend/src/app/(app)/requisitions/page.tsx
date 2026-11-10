"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, MapPin, Search, UserRound } from "lucide-react";
import {
  Avatar, Card, cx, Drawer, Empty, ErrorNote, PageHeader, Skeleton, StageBadge, StatusPill, td, tdNum, th, thNum,
} from "@/components/ui";
import type { ApplicationRow, Dashboard, HistoryRow, PipelineRow } from "@/lib/api";
import { useApi } from "@/lib/useApi";

function StageTimeline({ applicationId }: { applicationId: string }) {
  const { data, error } = useApi<HistoryRow[]>(`/api/applications/${encodeURIComponent(applicationId)}/history`);
  if (error) return <ErrorNote message={error} />;
  if (!data) return <Skeleton className="h-20" />;
  return (
    <ol className="relative ml-1.5 border-l border-line pl-5">
      {data.map((h, i) => (
        <li key={i} className="relative pb-3 last:pb-0">
          <span className="absolute -left-[26px] top-1 size-2.5 rounded-full ring-2 ring-surface" style={{ background: `var(--stage-${h.stage.toLowerCase()})` }} aria-hidden />
          <div className="text-sm font-medium text-ink">{h.stage}</div>
          <div className="tabular text-xs text-ink-3">
            {h.from.slice(0, 16)} {h.to ? `→ ${h.to.slice(0, 16)}` : "→ now"}
          </div>
        </li>
      ))}
    </ol>
  );
}

function RequisitionPanel({ req, onClose }: { req: PipelineRow | null; onClose: () => void }) {
  const { data, error } = useApi<ApplicationRow[]>(req ? `/api/requisitions/${encodeURIComponent(req.req_id)}/applications` : null);
  const [openApp, setOpenApp] = useState<string | null>(null);
  const [stage, setStage] = useState<string>("All");
  const rows = useMemo(() => (data ?? []).filter((a) => stage === "All" || a.current_stage === stage), [data, stage]);
  const stages = useMemo(() => ["All", ...Array.from(new Set((data ?? []).map((a) => a.current_stage)))], [data]);

  return (
    <Drawer
      open={!!req}
      onClose={() => { setOpenApp(null); setStage("All"); onClose(); }}
      title={req ? <span className="flex items-center gap-2">{req.title} <StatusPill status={req.status} /></span> : ""}
      subtitle={req && <span className="flex items-center gap-1"><span>{req.req_id} · {req.department}</span><span className="mx-1">·</span><MapPin size={13} />{req.location}</span>}
    >
      {req && (
        <>
          <div className="grid grid-cols-2 gap-px border-b border-line bg-line sm:grid-cols-4">
            {[["Applications", req.applications], ["In progress", req.in_progress], ["At offer", req.at_offer], ["Hired", req.hired]].map(([k, v]) => (
              <div key={k} className="bg-surface px-5 py-4">
                <div className="text-xs text-ink-3">{k}</div>
                <div className="tabular mt-0.5 text-xl font-semibold text-ink">{v}</div>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 border-b border-line px-6 py-3 text-sm text-ink-2">
            <span><span className="text-ink-3">Hiring manager</span> {req.hiring_manager}</span>
            <span><span className="text-ink-3">Recruiter</span> {req.recruiter}</span>
            <span><span className="text-ink-3">Headcount</span> {req.headcount}</span>
          </div>

          <div className="flex flex-wrap gap-1.5 px-6 pt-4">
            {stages.map((s) => (
              <button key={s} onClick={() => setStage(s)}
                className={cx("rounded-full border px-2.5 py-1 text-xs font-medium transition", stage === s ? "border-accent bg-accent-soft text-accent" : "border-line text-ink-2 hover:bg-surface-2")}>
                {s}
              </button>
            ))}
          </div>

          <div className="px-3 py-3">
            {error && <ErrorNote message={error} />}
            {!data && !error && <div className="space-y-2 px-3">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-12" />)}</div>}
            {data && !rows.length && <Empty title="No applications in this stage" />}
            <ul className="divide-y divide-line">
              {rows.map((a) => (
                <li key={a.application_id}>
                  <button onClick={() => setOpenApp(openApp === a.application_id ? null : a.application_id)}
                    className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left hover:bg-surface-2" aria-expanded={openApp === a.application_id}>
                    <Avatar name={a.candidate_name} size={34} />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-ink">{a.candidate_name}</div>
                      <div className="tabular text-xs text-ink-3">{a.application_id} · applied {a.applied_on}{a.hired_on ? ` · hired ${a.hired_on}` : ""}</div>
                    </div>
                    <StageBadge stage={a.current_stage} />
                    {openApp === a.application_id ? <ChevronDown size={16} className="text-ink-3" /> : <ChevronRight size={16} className="text-ink-3" />}
                  </button>
                  {openApp === a.application_id && (
                    <div className="px-6 pb-4 pt-1"><StageTimeline applicationId={a.application_id} /></div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </Drawer>
  );
}

export default function RequisitionsPage() {
  const { data, error } = useApi<Dashboard>("/api/dashboard");
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("All");
  const [status, setStatus] = useState("All");
  const [selected, setSelected] = useState<PipelineRow | null>(null);

  const all = data?.pipeline_by_requisition.value ?? [];
  const depts = useMemo(() => ["All", ...Array.from(new Set(all.map((r) => r.department))).sort()], [all]);
  const rows = all.filter(
    (r) =>
      (dept === "All" || r.department === dept) &&
      (status === "All" || r.status === status) &&
      (!q || `${r.req_id} ${r.title} ${r.hiring_manager} ${r.recruiter} ${r.location}`.toLowerCase().includes(q.toLowerCase())),
  );

  const chip = (active: boolean) =>
    cx("rounded-full border px-3 py-1.5 text-xs font-medium transition", active ? "border-accent bg-accent-soft text-accent" : "border-line bg-surface text-ink-2 hover:bg-surface-2");

  return (
    <>
      <PageHeader title="Requisitions" subtitle="Current pipeline per role. Select a requisition to see its candidates and their stage history." />
      {error && <ErrorNote message={error} />}

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-1.5">
          {depts.map((d) => <button key={d} onClick={() => setDept(d)} className={chip(dept === d)}>{d}</button>)}
          <span className="mx-1 hidden w-px bg-line sm:block" />
          {["All", "open", "closed"].map((s) => <button key={s} onClick={() => setStatus(s)} className={chip(status === s) + " capitalize"}>{s}</button>)}
        </div>
        <label className="relative block lg:w-72">
          <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search role, id, person…" aria-label="Search requisitions"
            className="w-full rounded-lg border border-line bg-surface py-2 pl-9 pr-3 text-sm text-ink outline-none focus:border-accent" />
        </label>
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-line bg-surface-2">
              <tr>
                <th className={th}>Requisition</th><th className={th}>Department</th><th className={th}>Owners</th><th className={th}>Status</th>
                <th className={thNum}>Applications</th><th className={thNum}>In progress</th><th className={thNum}>At offer</th><th className={thNum}>Hired</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {!data && Array.from({ length: 6 }, (_, i) => <tr key={i}><td colSpan={8} className="px-4 py-3"><Skeleton className="h-8" /></td></tr>)}
              {rows.map((r) => (
                <tr key={r.req_id} onClick={() => setSelected(r)} className="cursor-pointer transition hover:bg-surface-2"
                  tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setSelected(r)}>
                  <td className={td}>
                    <div className="font-medium text-ink">{r.title}</div>
                    <div className="flex items-center gap-1 text-xs text-ink-3">{r.req_id} · <MapPin size={11} />{r.location}</div>
                  </td>
                  <td className={td}>{r.department}</td>
                  <td className={td}>
                    <div className="flex items-center gap-1.5 text-xs"><UserRound size={12} className="text-ink-3" />{r.hiring_manager}</div>
                    <div className="text-xs text-ink-3">Recruiter: {r.recruiter}</div>
                  </td>
                  <td className={td}><StatusPill status={r.status} /></td>
                  <td className={tdNum}>{r.applications}</td>
                  <td className={tdNum}>{r.in_progress}</td>
                  <td className={tdNum}>{r.at_offer}</td>
                  <td className={tdNum}>{r.hired}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data && !rows.length && <Empty title="No requisitions match" hint="Clear a filter or the search." />}
        </div>
      </Card>

      <RequisitionPanel req={selected} onClose={() => setSelected(null)} />
    </>
  );
}
