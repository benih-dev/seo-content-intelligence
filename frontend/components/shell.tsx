"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeSelect } from "@/components/theme-select";
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
  Sparkles,
} from "lucide-react";

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
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
              <strong>Editorial workspace</strong>
              <small>Local · Single operator</small>
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
              {path.startsWith("/runs/") ? "Content workbench" : "Projects"}
            </strong>
          </span>
          <div className="topbar-actions">
            <span className="topbar-right">
              <span className="live-dot" /> Evidence-led publishing{" "}
              <Sparkles size={15} />
            </span>
            <ThemeSelect />
          </div>
        </header>
        <main id="main">{children}</main>
        <footer className="main-footer">
          SEO Content Intelligence{" "}
          <span>Built for thoughtful content, not content at scale.</span>
        </footer>
      </div>
    </div>
  );
}
