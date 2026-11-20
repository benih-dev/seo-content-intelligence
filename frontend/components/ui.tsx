"use client";
import { AlertCircle, ArrowRight, Check, LoaderCircle } from "lucide-react";
import { label } from "@/lib/api";

export function Badge({
  value,
  children,
}: {
  value: string;
  children?: React.ReactNode;
}) {
  const tone = [
    "exported",
    "article_ready",
    "pass",
    "approved",
    "done",
  ].includes(value)
    ? "green"
    : ["failed", "blocked", "blocker"].includes(value)
      ? "red"
      : value.includes("review") ||
          value === "major" ||
          value === "needs_verification"
        ? "amber"
        : "blue";
  return (
    <span className={`badge ${tone}`}>
      <span />
      {children || label(value)}
    </span>
  );
}
export function ErrorNotice({ error }: { error: string }) {
  return error ? (
    <div className="notice error" role="alert">
      <AlertCircle size={17} />
      <div>{error}</div>
    </div>
  ) : null;
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-symbol">◇</span>
      <h3>{title}</h3>
      <p>{children || "This stage will appear here as your run progresses."}</p>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={20} />
      Loading workspace…
    </div>
  );
}
export function Submit({
  busy,
  children,
}: {
  busy: boolean;
  children: React.ReactNode;
}) {
  return (
    <button type="submit" className="button primary" disabled={busy}>
      {busy ? <LoaderCircle size={16} className="spin" /> : <Check size={16} />}{" "}
      {children}
    </button>
  );
}
export function Panel({
  title,
  eyebrow,
  aside,
  children,
}: {
  title: string;
  eyebrow?: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          <h2>{title}</h2>
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}
export function SectionTitle({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">YOUR EDITORIAL WORKSPACE</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children}
    </div>
  );
}
export function NextArrow() {
  return <ArrowRight size={16} />;
}
