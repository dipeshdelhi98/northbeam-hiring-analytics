"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, BarChart3, Loader2, ShieldCheck } from "lucide-react";
import { useAuth } from "@/components/auth";
import { cx, RoleBadge } from "@/components/ui";
import type { Role } from "@/lib/api";

// Demo accounts (synthetic data). The password is the documented demo password from the README.
const DEMO: { email: string; name: string; role: Role; note: string }[] = [
  { email: "simran.jain@northbeam.example", name: "Simran Jain", role: "admin", note: "Everything; ties to the control totals" },
  { email: "naveen.malhotra@northbeam.example", name: "Naveen Malhotra", role: "recruiter", note: "The 7 requisitions they own" },
  { email: "uday.varma@northbeam.example", name: "Uday Varma", role: "hiring_manager", note: "REQ-1003, 1010, 1024 only" },
];

export default function LoginPage() {
  const { me, ready, signIn } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ready && me) router.replace("/");
  }, [ready, me, router]);

  const submit = async (e?: React.FormEvent, creds?: { email: string; password: string }) => {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(creds?.email ?? email, creds?.password ?? password);
    } catch (x) {
      setError((x as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-accent lg:block">
        <div className="absolute inset-0 opacity-[0.12]" style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)", backgroundSize: "22px 22px" }} />
        <div className="relative flex h-full flex-col justify-between p-12 text-white">
          <div className="flex items-center gap-2.5 text-lg font-semibold">
            <span className="grid size-9 place-items-center rounded-lg bg-white/15"><BarChart3 size={19} /></span>
            Northbeam Partners
          </div>
          <div className="max-w-md">
            <h1 className="text-4xl font-semibold leading-tight tracking-tight">One set of hiring numbers everyone agrees on.</h1>
            <p className="mt-4 text-white/80">
              Pipeline, time to hire and offer acceptance from a single metric layer, with each
              person seeing only the requisitions they are responsible for.
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm text-white/70"><ShieldCheck size={16} /> Access is scoped on the server for every request.</div>
        </div>
      </div>

      <div className="flex items-center justify-center px-4 py-12 sm:px-8">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <span className="grid size-9 place-items-center rounded-lg bg-accent text-white"><BarChart3 size={19} /></span>
            <span className="text-lg font-semibold">Northbeam</span>
          </div>
          <h2 className="text-2xl font-semibold tracking-tight">Sign in</h2>
          <p className="mt-1 text-sm text-ink-3">Use a Northbeam email from the data pack.</p>

          <form onSubmit={submit} className="mt-6 flex flex-col gap-3">
            <label className="text-sm font-medium text-ink-2">
              Email
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username"
                className="mt-1.5 w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
                placeholder="name@northbeam.example" />
            </label>
            <label className="text-sm font-medium text-ink-2">
              Password
              <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
                className="mt-1.5 w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent/20" />
            </label>
            {error && <div className="rounded-lg bg-bad-soft px-3 py-2 text-sm text-bad">{error}</div>}
            <button disabled={busy} className="mt-1 flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 font-medium text-white transition hover:opacity-90 disabled:opacity-60">
              {busy ? <Loader2 size={17} className="animate-spin" /> : null} Sign in
            </button>
          </form>

          <div className="mt-8">
            <div className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-3">Demo accounts</div>
            <div className="flex flex-col gap-2">
              {DEMO.map((d) => (
                <button key={d.email} disabled={busy}
                  onClick={() => { setEmail(d.email); setPassword("northbeam-demo"); submit(undefined, { email: d.email, password: "northbeam-demo" }); }}
                  className={cx("group flex items-center justify-between gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-left transition hover:border-accent/50 hover:bg-accent-soft/40")}>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-sm font-semibold text-ink">{d.name} <RoleBadge role={d.role} /></div>
                    <div className="mt-0.5 truncate text-xs text-ink-3">{d.note}</div>
                  </div>
                  <ArrowRight size={16} className="shrink-0 text-ink-3 transition group-hover:translate-x-0.5 group-hover:text-accent" />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
