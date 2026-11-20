"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, authPath } from "@/lib/api";
import { ErrorNotice, Loading } from "@/components/ui";
import { ThemeSelect } from "@/components/theme-select";
import { TextSizeSelect } from "@/components/text-size-select";
import {
  ArrowUpRight,
  Boxes,
  CircleHelp,
  Command,
  FolderOpen,
  Layers3,
  PanelLeft,
  Plus,
  ShieldCheck,
  ScrollText,
  Settings,
  Sparkles,
} from "lucide-react";

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [account, setAccount] = useState<{ username: string }>();
  const [error, setError] = useState("");
  const publicPage = path === "/login" || path === "/setup";
  useEffect(() => {
    let live = true;
    async function check() {
      try {
        const status = await api<{ setup_required: boolean }>("/auth/status");
        if (!live) return;
        if (status.setup_required) {
          if (path !== "/setup") router.replace(authPath(true));
          return;
        }
        if (path === "/setup") { router.replace("/login"); return; }
        try {
          const user = await api<{ username: string }>("/auth/me");
          if (live) { setAccount(user); if (publicPage) router.replace("/"); }
        } catch {
          if (live && !publicPage) router.replace("/login");
        }
      } catch {
        if (live) setError("Unable to check your session. Please reload to retry.");
      }
    }
    void check();
    return () => { live = false; };
  }, [path, publicPage, router]);

  async function logout() {
    try {
      await api("/auth/logout", {});
      setAccount(undefined);
      router.replace("/login");
    } catch { setError("Sign out failed. Please retry."); }
  }

  if (publicPage || !account) {
    return <div className="auth-shell">
      <header className="topbar"><strong>Content Intelligence</strong><div className="topbar-actions"><ThemeSelect /><TextSizeSelect /></div></header>
      <main id="main" className="auth-main"><ErrorNotice error={error} />{publicPage ? children : !error && <Loading />}</main>
    </div>;
  }
  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Workspace navigation">
        <Link href="/" className="brand">
          <span className="brand-icon">
            <Layers3 size={20} />
          </span>
          Content Intelligence<span className="brand-dot">.</span>
        </Link>
        <div className="workspace">
          <span className="workspace-avatar">S</span>
          <div>
            <strong>SEO workspace</strong>
            <small>Editorial operations</small>
          </div>
          <Command size={14} />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <Link
            href="/"
            className={
              path === "/" || path.startsWith("/projects")
                ? "nav-link active"
                : "nav-link"
            }
          >
            <FolderOpen size={17} />
            Projects<span className="nav-shortcut">⌘ K</span>
          </Link>
          <Link
            href="/runs/new"
            className={
              path.startsWith("/runs") ? "nav-link active" : "nav-link"
            }
          >
            <Boxes size={17} />
            Content runs
          </Link>
          <Link href="/settings" className={path === "/settings" ? "nav-link active" : "nav-link"}>
            <Settings size={17} /> Settings
          </Link>
          <Link href="/logs" className={path === "/logs" ? "nav-link active" : "nav-link"}>
            <ScrollText size={17} /> Logs
          </Link>
        </nav>
        <Link className="sidebar-create" href="/projects/new">
          <Plus size={16} /> Create a project
        </Link>
        <div className="sidebar-bottom">
          <div className="safety-note">
            <ShieldCheck size={19} />
            <strong>Human-led. Evidence-first.</strong>
            <p>
              Three review gates. Every decision traceable. You stay in control.
            </p>
          </div>
          <a
            href="https://app.devin.ai/sessions/1444ec1e4a1c45168c085bb3d8839c10"
            target="_blank"
            rel="noreferrer"
            className="request-link"
          >
            <CircleHelp size={15} />
            Request changes
            <ArrowUpRight size={14} />
          </a>
          <div className="operator">
            <span className="operator-avatar">EW</span>
            <div>
              <strong>{account.username}</strong>
              <button className="button" type="button" onClick={logout}>Log out</button>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span className="topbar-title">
            <PanelLeft size={16} />
            Workspace <span>/</span>{" "}
            <strong>
              {path.startsWith("/runs/") ? "Content workbench" : path === "/settings" ? "Settings" : path === "/logs" ? "Logs" : "Projects"}
            </strong>
          </span>
          <div className="topbar-actions">
            <span className="topbar-right">
              <span className="live-dot" /> Evidence-led publishing{" "}
              <Sparkles size={15} />
            </span>
            <ThemeSelect />
            <TextSizeSelect />
          </div>
        </header>
        <main id="main"><ErrorNotice error={error} />{children}</main>
        <footer className="main-footer">
          SEO Content Intelligence{" "}
          <span>Built for thoughtful content, not content at scale.</span>
        </footer>
      </div>
    </div>
  );
}
