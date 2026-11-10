"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BarChart3, Briefcase, LogOut, Menu, Moon, ShieldCheck, Sun, Users } from "lucide-react";
import { useAuth } from "@/components/auth";
import { Avatar, cx, RoleBadge, Skeleton } from "@/components/ui";

const NAV = [
  { href: "/", label: "Overview", icon: BarChart3 },
  { href: "/requisitions/", label: "Requisitions", icon: Briefcase },
  { href: "/team/", label: "Team", icon: Users },
];

function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const t = document.documentElement.dataset.theme;
    setDark(t ? t === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches);
  }, []);
  const toggle = () => {
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("nb.theme", next); } catch {}
    setDark(!dark);
  };
  return (
    <button onClick={toggle} className="rounded-lg p-2 text-ink-3 hover:bg-surface-2 hover:text-ink" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}>
      {dark ? <Sun size={17} /> : <Moon size={17} />}
    </button>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid size-8 place-items-center rounded-lg bg-accent text-white">
        <BarChart3 size={17} />
      </span>
      <div className="leading-tight">
        <div className="text-[14px] font-semibold text-ink">Northbeam</div>
        <div className="text-[11px] text-ink-3">Hiring analytics</div>
      </div>
    </div>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const { me, ready, signOut } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (ready && !me) router.replace("/login/");
  }, [ready, me, router]);
  useEffect(() => setMobileOpen(false), [path]);

  if (!ready || !me) {
    return (
      <div className="mx-auto max-w-6xl p-8">
        <Skeleton className="mb-6 h-8 w-64" />
        <div className="grid gap-4 sm:grid-cols-3"><Skeleton className="h-32" /><Skeleton className="h-32" /><Skeleton className="h-32" /></div>
      </div>
    );
  }

  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));

  const nav = (
    <nav className="flex flex-col gap-1">
      {NAV.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          className={cx(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            isActive(href) ? "bg-accent-soft text-accent" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
          )}
        >
          <Icon size={17} /> {label}
        </Link>
      ))}
    </nav>
  );

  const scopeNote = (
    <div className="rounded-xl border border-line bg-surface-2 p-3 text-xs text-ink-2">
      <div className="mb-1 flex items-center gap-1.5 font-semibold text-ink"><ShieldCheck size={14} /> Your access</div>
      {me.role === "admin"
        ? "All requisitions and candidates."
        : me.requisitions.length
          ? `${me.requisitions.length} requisition${me.requisitions.length > 1 ? "s" : ""} you ${me.role === "recruiter" ? "own as recruiter" : "manage"}, and the candidates against them.`
          : "No requisitions assigned."}
    </div>
  );

  const userBlock = (
    <div className="flex items-center gap-3 border-t border-line pt-4">
      <Avatar name={me.name} size={36} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold text-ink">{me.name}</div>
        <RoleBadge role={me.role} />
      </div>
      <button onClick={signOut} className="rounded-lg p-2 text-ink-3 hover:bg-surface-2 hover:text-ink" aria-label="Sign out" title="Sign out">
        <LogOut size={17} />
      </button>
    </div>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen flex-col gap-6 border-r border-line bg-surface px-4 py-5 lg:flex">
        <div className="flex items-center justify-between"><Brand /><ThemeToggle /></div>
        {nav}
        <div className="mt-auto flex flex-col gap-4">{scopeNote}{userBlock}</div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-surface px-4 py-3 lg:hidden">
        <Brand />
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <button onClick={() => setMobileOpen((o) => !o)} className="rounded-lg p-2 text-ink-2 hover:bg-surface-2" aria-label="Menu">
            <Menu size={19} />
          </button>
        </div>
      </header>
      {mobileOpen && (
        <div className="sticky top-[57px] z-20 flex flex-col gap-4 border-b border-line bg-surface p-4 shadow-lg lg:hidden">
          {nav}{scopeNote}{userBlock}
        </div>
      )}

      <main className="min-w-0 px-4 py-6 sm:px-8 sm:py-8">
        <div className="mx-auto max-w-7xl">{children}</div>
      </main>
    </div>
  );
}
