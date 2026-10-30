import React from "react";
import { Activity, AlertCircle, ArrowDown, ArrowRight, ArrowUpRight, Clock3, ShieldCheck } from "lucide-react";

export function Card({ children, className = "", title, subtitle, action }) {
  return (
    <section className={"panel " + className}>
      {(title || action) && (
        <div className="panel-head">
          <div>
            {title && <h2 className="panel-title">{title}</h2>}
            {subtitle && <p className="panel-subtitle">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Badge({ children, tone = "neutral", dot = false }) {
  return <span className={"badge badge-" + tone}>{dot && <i />} {children}</span>;
}

export function RiskBadge({ risk }) {
  const tone = risk === "Critical" || risk === "High" ? "critical" :
    risk === "Watch" || risk === "Medium" ? "warning" :
    risk === "Healthy" || risk === "Delivered" || risk === "Approved" ? "good" :
    risk === "Delayed" || risk === "Revision Requested" ? "warning" :
    risk === "Rejected" ? "neutral" : "neutral";
  return <Badge tone={tone} dot>{risk || "Unknown"}</Badge>;
}

export function PageHeading({ eyebrow, title, description, actions }) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="heading-actions">{actions}</div>}
    </div>
  );
}

export function StatCard({ label, value, note, icon: Icon, accent = "green", onClick }) {
  return (
    <button className={"stat-card stat-" + accent} onClick={onClick} type="button">
      <div className="stat-top"><span>{label}</span><span className="stat-icon"><Icon size={17} strokeWidth={1.8} /></span></div>
      <div className="stat-value">{value ?? "—"}</div>
      <div className="stat-note">{note}</div>
    </button>
  );
}

export function EmptyState({ title, description, icon: Icon = Activity, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon"><Icon size={20} /></span>
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function LoadingState({ label = "Loading demo data" }) {
  return <div className="loading-state"><span className="spinner" />{label}</div>;
}

export function ErrorBanner({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="error-banner" role="alert">
      <AlertCircle size={18} />
      <span>{message}</span>
      {onRetry && <button onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function formatDate(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(date);
}

export function formatDateOnly(value) {
  if (!value) return "Not available";
  const parts = String(value).split("-").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return value;
  return new Intl.DateTimeFormat(undefined, { year:"numeric", month:"short", day:"numeric", timeZone:"UTC" }).format(new Date(Date.UTC(parts[0],parts[1]-1,parts[2])));
}

export function fmt(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(Number(value));
}

export function SectionLabel({ children }) {
  return <div className="section-label">{children}</div>;
}

export function FlowLine({ children }) {
  return <div className="flow-line">{children}</div>;
}

export function ChangeIcon({ direction }) {
  return direction === "down" ? <ArrowDown size={15} /> : direction === "up" ? <ArrowUpRight size={15} /> : <ArrowRight size={15} />;
}
