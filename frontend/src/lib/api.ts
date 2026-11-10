/**
 * The only module that talks to the backend.
 *
 * Contract with the API: every number shown in the UI arrives either as a pre-formatted
 * `display` string or as a raw count to be placed in a table/chart as-is. Nothing in this app
 * derives a metric — tests/test_single_definition.py greps src/ to keep it that way.
 */

const TOKEN_KEY = "nb.token";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage blocked: session lasts for this page only */
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    if (res.status === 401 && token) {
      setToken(null);
      window.dispatchEvent(new Event("nb:signed-out"));
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

// ---- response types (mirror api/main.py + metrics/definitions.py) ----

export type Role = "admin" | "recruiter" | "hiring_manager";

export interface Me {
  user_id: string;
  name: string;
  role: Role;
  email: string;
  requisitions: string[];
}

export interface MetricResult<V = number | null> {
  name: string;
  label: string;
  unit: string;
  value: V;
  display: string;
  params: Record<string, string | null>;
  description: string;
}

export interface PeriodOverPeriod {
  name: string;
  label: string;
  current: MetricResult;
  previous: MetricResult;
  display: string;
  change_display: string;
  direction: "up" | "down" | "flat" | null;
  favourable: boolean | null;
  previous_window: string;
}

export interface ConversionRow {
  from_stage: string;
  to_stage: string;
  reached_from: number;
  reached_to: number;
  display: string;
}

export interface PipelineRow {
  req_id: string;
  title: string;
  department: string;
  status: string;
  location: string;
  hiring_manager: string;
  recruiter: string;
  headcount: number;
  applications: number;
  in_progress: number;
  at_offer: number;
  hired: number;
}

export interface MonthRow {
  month: string;
  month_label: string;
  hires: number;
  median_days: number | null;
  median_days_display: string;
}

export interface Dashboard {
  cards: MetricResult[];
  period_over_period: PeriodOverPeriod;
  stage_conversion: MetricResult<ConversionRow[]>;
  pipeline_by_requisition: MetricResult<PipelineRow[]>;
  hires_by_month: MetricResult<MonthRow[]>;
}

export interface TeamRow {
  user_id: string;
  name: string;
  role: Role;
  department: string | null;
  requisitions: number;
  applications: number;
  in_progress: number;
  hires: number;
  median_days: number | null;
  median_days_display: string;
  acceptance_pct: number | null;
  acceptance_display: string;
}

export interface ApplicationRow {
  application_id: string;
  candidate_name: string;
  applied_on: string;
  current_stage: string;
  hired_on: string | null;
}

export interface HistoryRow {
  stage: string;
  from: string;
  to: string | null;
}
