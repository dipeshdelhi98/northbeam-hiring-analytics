"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, CalendarClock, Clock, IndianRupee, Percent, Users } from "lucide-react";
import { useAuth } from "@/components/auth";
import { FunnelChart, HiresByMonthChart } from "@/components/charts";
import {
  Card, CardHeader, Empty, ErrorNote, PageHeader, Skeleton, StatTile, StatusPill, td, tdNum, th, thNum,
} from "@/components/ui";
import type { Dashboard, MetricResult } from "@/lib/api";
import { useApi } from "@/lib/useApi";

const ICONS: Record<string, React.ReactNode> = {
  candidate_pool: <Users size={16} />,
  applications_in_stage_as_of: <CalendarClock size={16} />,
  time_to_hire_median_days: <Clock size={16} />,
  offered_salary_total_inr: <IndianRupee size={16} />,
  offer_acceptance_rate: <Percent size={16} />,
};

/** Human-readable parameter line under each tile (pure string formatting). */
function paramHint(m: MetricResult): string {
  const p = m.params;
  if (p.as_of) return `${p.stage} at close of ${p.as_of}`;
  if (p.start && p.end) return `Hires ${p.start} → ${p.end}`;
  if (p.department) return `${p.department} requisitions, any status`;
  if (m.name === "offer_acceptance_rate") return "Decided offers only";
  if (m.name === "candidate_pool") return "People, not candidate records";
  return "";
}

const STAGES = ["Applied", "Screen", "Interview", "Offer", "Hired", "Rejected", "Withdrawn"];

function AsOfExplorer() {
  const [stage, setStage] = useState("Offer");
  const [asOf, setAsOf] = useState("2026-03-31");
  const { data, loading, error } = useApi<MetricResult>(
    asOf ? `/api/metrics/applications_in_stage_as_of?stage=${stage}&as_of=${asOf}` : null,
  );
  const field = "rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent";
  return (
    <Card>
      <CardHeader title="Pipeline on any date" subtitle="Rebuilt from stage history, not today's status column" />
      <div className="flex flex-col gap-4 p-5">
        <div className="flex flex-wrap gap-2">
          <select value={stage} onChange={(e) => setStage(e.target.value)} className={field} aria-label="Stage">
            {STAGES.map((s) => <option key={s}>{s}</option>)}
          </select>
          <input type="date" value={asOf} min="2025-09-01" max="2026-10-31" onChange={(e) => setAsOf(e.target.value)} className={field} aria-label="As of date" />
        </div>
        <div className="rounded-xl bg-surface-2 p-5">
          <div className="text-[13px] text-ink-3">Applications in <span className="font-medium text-ink-2">{stage}</span> at close of {asOf || "…"}</div>
          <div className="tabular mt-1 text-4xl font-semibold tracking-tight text-ink">
            {error ? "–" : loading && !data ? <Skeleton className="h-10 w-20" /> : data?.display}
          </div>
        </div>
        {error && <ErrorNote message={error} />}
      </div>
    </Card>
  );
}

export default function OverviewPage() {
  const { me } = useAuth();
  const { data, error } = useApi<Dashboard>("/api/dashboard");

  return (
    <>
      <PageHeader
        title={`Good to see you, ${me?.name.split(" ")[0]}`}
        subtitle={me?.role === "admin" ? "Across all Northbeam requisitions" : `Across your ${me?.requisitions.length} requisition${me?.requisitions.length === 1 ? "" : "s"}: ${me?.requisitions.join(", ")}`}
      />
      {error && <ErrorNote message={error} />}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {data
          ? data.cards.map((c) => <StatTile key={c.name} label={c.label} value={c.display} hint={paramHint(c)} icon={ICONS[c.name]} />)
          : Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-[132px]" />)}
        {data ? (
          <StatTile
            label="Time to hire, Q2 vs Q1 2026"
            value={data.period_over_period.current.display}
            icon={<Clock size={16} />}
            delta={{ text: data.period_over_period.change_display, direction: data.period_over_period.direction, favourable: data.period_over_period.favourable }}
            hint={`Compared with ${data.period_over_period.previous_window} (${data.period_over_period.previous.display})`}
          />
        ) : <Skeleton className="h-[132px]" />}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader title="Hires by month" subtitle="Hover a month for its median time to hire" />
          <div className="p-4 pt-2">
            {data ? (data.hires_by_month.value.length ? <HiresByMonthChart rows={data.hires_by_month.value} /> : <Empty title="No hires yet" />) : <Skeleton className="h-[260px]" />}
          </div>
        </Card>
        <Card className="xl:col-span-2">
          <CardHeader title="Stage funnel" subtitle="Applications that ever reached each stage" />
          <div className="p-4 pt-2">
            {data ? <FunnelChart rows={data.stage_conversion.value} /> : <Skeleton className="h-[260px]" />}
          </div>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-5">
        <div className="min-w-0 xl:col-span-2"><AsOfExplorer /></div>
        <Card className="xl:col-span-3">
          <CardHeader
            title="Stage conversion"
            subtitle="Share of applications reaching the next stage"
            right={<Link href="/requisitions/" className="flex items-center gap-1 text-sm font-medium text-accent hover:underline">Requisitions <ArrowRight size={14} /></Link>}
          />
          <div className="mt-3 overflow-x-auto">
            <table className="w-full">
              <thead className="border-y border-line bg-surface-2"><tr><th className={th}>Step</th><th className={thNum}>Reached from</th><th className={thNum}>Reached to</th><th className={thNum}>Conversion</th></tr></thead>
              <tbody className="divide-y divide-line">
                {data?.stage_conversion.value.map((r) => (
                  <tr key={r.from_stage}>
                    <td className={td}>{r.from_stage} → {r.to_stage}</td>
                    <td className={tdNum}>{r.reached_from}</td>
                    <td className={tdNum}>{r.reached_to}</td>
                    <td className={tdNum + " font-semibold"}>{r.display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader title="Busiest open requisitions" subtitle="Applications currently in progress" />
        <div className="mt-3 overflow-x-auto">
          <table className="w-full">
            <thead className="border-y border-line bg-surface-2"><tr><th className={th}>Requisition</th><th className={th}>Department</th><th className={th}>Status</th><th className={thNum}>In progress</th><th className={thNum}>At offer</th><th className={thNum}>Hired</th></tr></thead>
            <tbody className="divide-y divide-line">
              {data?.pipeline_by_requisition.value
                .filter((r) => r.status === "open")
                .sort((a, b) => b.in_progress - a.in_progress)
                .slice(0, 6)
                .map((r) => (
                  <tr key={r.req_id}>
                    <td className={td}><div className="font-medium text-ink">{r.title}</div><div className="text-xs text-ink-3">{r.req_id} · {r.location}</div></td>
                    <td className={td}>{r.department}</td>
                    <td className={td}><StatusPill status={r.status} /></td>
                    <td className={tdNum}>{r.in_progress}</td>
                    <td className={tdNum}>{r.at_offer}</td>
                    <td className={tdNum}>{r.hired}</td>
                  </tr>
                ))}
            </tbody>
          </table>
          {data && !data.pipeline_by_requisition.value.some((r) => r.status === "open") && <Empty title="No open requisitions in your scope" />}
        </div>
      </Card>
    </>
  );
}
