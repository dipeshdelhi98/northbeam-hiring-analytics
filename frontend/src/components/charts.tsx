"use client";

/**
 * Charts place API values on axes; they never derive new numbers. Specs follow the dataviz
 * method: one series = one hue (no legend box; the card title names it), bars ≤ 24px with 4px
 * rounded data-ends, hairline recessive grid, hover tooltip on every mark, table alternative
 * available on the page.
 */
import {
  Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { ConversionRow, MonthRow, TeamRow } from "@/lib/api";

function TipBox({ title, lines }: { title: string; lines: [string, string][] }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-semibold text-ink">{title}</div>
      {lines.map(([k, v]) => (
        <div key={k} className="flex items-center justify-between gap-6 text-ink-2">
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-sm" style={{ background: "var(--series-1)" }} aria-hidden />
            {k}
          </span>
          <span className="tabular font-medium text-ink">{v}</span>
        </div>
      ))}
    </div>
  );
}

const cursor = { fill: "var(--surface-2)" };

export function HiresByMonthChart({ rows }: { rows: MonthRow[] }) {
  return (
    <div className="h-[260px] w-full" role="img" aria-label="Column chart of hires per month">
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ top: 22, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid vertical={false} strokeWidth={1} />
          <XAxis dataKey="month_label" tickLine={false} axisLine={{ stroke: "var(--border)" }} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={44} />
          <Tooltip
            cursor={cursor}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const r = payload[0].payload as MonthRow;
              return <TipBox title={r.month_label} lines={[["Hires", String(r.hires)], ["Median time to hire", r.median_days_display]]} />;
            }}
          />
          <Bar dataKey="hires" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false}>
            <LabelList dataKey="hires" position="top" className="tabular" style={{ fill: "var(--text-2)", fontSize: 11 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Funnel: applications that ever reached each stage, labelled with the API's conversion string. */
export function FunnelChart({ rows }: { rows: ConversionRow[] }) {
  if (!rows.length) return null;
  const last = rows[rows.length - 1];
  const data = [
    ...rows.map((r) => ({ stage: r.from_stage, reached: r.reached_from, conv: "" })),
    { stage: last.to_stage, reached: last.reached_to, conv: "" },
  ];
  // conversion into each stage (from the previous one), as provided by the API
  rows.forEach((r, i) => (data[i + 1].conv = `${r.display} from ${r.from_stage}`));
  return (
    <div className="h-[260px] w-full" role="img" aria-label="Funnel of applications reaching each stage">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 56, left: 8, bottom: 0 }} barCategoryGap={10}>
          <CartesianGrid horizontal={false} strokeWidth={1} />
          <XAxis type="number" tickLine={false} axisLine={false} allowDecimals={false} />
          <YAxis type="category" dataKey="stage" tickLine={false} axisLine={false} width={74} />
          <Tooltip
            cursor={cursor}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const r = payload[0].payload as (typeof data)[number];
              return <TipBox title={r.stage} lines={[["Reached", String(r.reached)], ...(r.conv ? [["Conversion", r.conv] as [string, string]] : [])]} />;
            }}
          />
          <Bar dataKey="reached" fill="var(--series-1)" radius={[0, 4, 4, 0]} maxBarSize={24} isAnimationActive={false}>
            <LabelList dataKey="reached" position="right" style={{ fill: "var(--text-2)", fontSize: 12 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TeamHiresChart({ rows }: { rows: TeamRow[] }) {
  const data = rows.filter((r) => r.requisitions);
  return (
    <div className="w-full" style={{ height: 40 + data.length * 34 }} role="img" aria-label="Bar chart of hires per person">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, left: 8, bottom: 0 }} barCategoryGap={8}>
          <CartesianGrid horizontal={false} strokeWidth={1} />
          <XAxis type="number" tickLine={false} axisLine={false} allowDecimals={false} />
          <YAxis type="category" dataKey="name" tickLine={false} axisLine={false} width={128} />
          <Tooltip
            cursor={cursor}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const r = payload[0].payload as TeamRow;
              return <TipBox title={r.name} lines={[["Hires", String(r.hires)], ["Median time to hire", r.median_days_display], ["Offer acceptance", r.acceptance_display]]} />;
            }}
          />
          <Bar dataKey="hires" fill="var(--series-1)" radius={[0, 4, 4, 0]} maxBarSize={20} isAnimationActive={false}>
            <LabelList dataKey="hires" position="right" style={{ fill: "var(--text-2)", fontSize: 12 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
