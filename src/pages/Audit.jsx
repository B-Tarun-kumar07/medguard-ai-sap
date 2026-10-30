import React, { useMemo, useState } from "react";
import {
  Activity, AlertTriangle, CheckCircle2, ClipboardCheck, Database, Settings2, ShieldCheck, Truck,
} from "lucide-react";
import { Card, EmptyState, PageHeading, Badge, fmt, formatDate } from "../components";

const categories = [
  { value: "All", label: "All events" },
  { value: "agent.", label: "Agent activity" },
  { value: "human.", label: "Human decisions" },
  { value: "shipment.", label: "Shipments" },
  { value: "demo.", label: "Demo controls" },
];

function iconFor(type) {
  if (type.startsWith("agent.sensing")) return AlertTriangle;
  if (type.startsWith("agent.compliance") || type.startsWith("human.")) return ShieldCheck;
  if (type.startsWith("shipment.")) return Truck;
  if (type.startsWith("settings.")) return Settings2;
  if (type.startsWith("demo.")) return Database;
  return Activity;
}

function toneFor(type) {
  if (type.startsWith("human.")) return "audit-tone-violet";
  if (type.startsWith("shipment.")) return "audit-tone-blue";
  if (type.startsWith("agent.")) return "audit-tone-green";
  return "audit-tone-neutral";
}

export default function Audit({ data }) {
  const [filter, setFilter] = useState("All");
  const [query, setQuery] = useState("");
  const analytics = data.analytics || {};
  const rows = useMemo(() => (data.audit || []).filter((event) => {
    const typeMatch = filter === "All" || event.event_type.startsWith(filter);
    const text = (event.summary + " " + event.actor + " " + event.event_type).toLowerCase();
    return typeMatch && text.includes(query.toLowerCase());
  }), [data.audit, filter, query]);
  const agentEvents = data.audit.filter((event) => event.event_type.startsWith("agent.")).length;
  const shipmentEvents = data.audit.filter((event) => event.event_type.startsWith("shipment.")).length;

  return (
    <>
      <PageHeading eyebrow="TRACEABILITY & OUTCOMES" title="Audit & analytics" description="Chronological agent activity, reviewer decisions, shipment outcomes, and demo-response measures." />
      <div className="analytics-kpis">
        <div><span className="analytics-icon analytics-green"><Activity size={17} /></span><small>Disruptions seen</small><strong>{analytics.disruptions_seen || 0}</strong></div>
        <div><span className="analytics-icon analytics-violet"><ClipboardCheck size={17} /></span><small>Human decisions</small><strong>{analytics.approval_decisions || 0}</strong></div>
        <div><span className="analytics-icon analytics-blue"><Truck size={17} /></span><small>Recovery shipments delivered</small><strong>{analytics.recommended_shipments_delivered || 0}</strong></div>
        <div><span className="analytics-icon analytics-amber"><Database size={17} /></span><small>Units recovered</small><strong>{fmt(analytics.units_recovered)}</strong></div>
      </div>

      <div className="dashboard-grid audit-grid">
        <Card title="Response activity" subtitle="Recorded events by function">
          <div className="response-metrics">
            <div className="response-metric"><span className="response-metric-head"><Activity size={15} />Agent actions</span><strong>{agentEvents}</strong><div className="metric-bar"><i style={{ width: Math.min(100, agentEvents * 8) + "%" }} /></div><small>Sensing, planning, allocation, logistics, compliance</small></div>
            <div className="response-metric"><span className="response-metric-head"><ShieldCheck size={15} />Reviewer decisions</span><strong>{analytics.approval_decisions || 0}</strong><div className="metric-bar metric-bar-violet"><i style={{ width: Math.min(100, (analytics.approval_decisions || 0) * 25) + "%" }} /></div><small>{analytics.pending || 0} decision(s) still pending</small></div>
            <div className="response-metric"><span className="response-metric-head"><Truck size={15} />Shipment updates</span><strong>{shipmentEvents}</strong><div className="metric-bar metric-bar-blue"><i style={{ width: Math.min(100, shipmentEvents * 12) + "%" }} /></div><small>Only real after a human approval</small></div>
          </div>
          <div className="audit-guardrail"><ShieldCheck size={15} /><span>Approvals, revisions, rejects, and delivery status changes are append-only audit events in the local SQLite database.</span></div>
        </Card>

        <Card title="Event mix" subtitle="Current local demo history">
          <div className="event-mix">
            {[
              ["Agent workflow", agentEvents, "mix-green"],
              ["Human decisions", analytics.approval_decisions || 0, "mix-violet"],
              ["Shipments", shipmentEvents, "mix-blue"],
              ["Other / system", Math.max(0, (analytics.audit_events || 0) - agentEvents - shipmentEvents - (analytics.approval_decisions || 0)), "mix-gray"],
            ].map(([label, value, color]) => (
              <div className="event-mix-row" key={label}><span><i className={color} />{label}</span><strong>{value}</strong></div>
            ))}
          </div>
          <div className="event-mix-foot"><span>Stored events</span><strong>{analytics.audit_events || 0}</strong></div>
          <Badge tone="neutral">Fictional data</Badge>
        </Card>
      </div>

      <Card title="Chronological event history" subtitle="Newest first · decisions include reviewer name, timestamp, and reason">
        <div className="audit-toolbar">
          <label className="search-field"><Activity size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search events or reviewer" /></label>
          <select className="select-field" value={filter} onChange={(event) => setFilter(event.target.value)} aria-label="Filter audit events">
            {categories.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
          </select>
          <span className="toolbar-count">{rows.length} events</span>
        </div>
        {rows.length ? (
          <div className="audit-timeline">
            {rows.map((event) => {
              const Icon = iconFor(event.event_type);
              return (
                <article className="audit-event" key={event.id}>
                  <div className={"audit-event-icon " + toneFor(event.event_type)}><Icon size={16} /></div>
                  <div className="audit-event-copy">
                    <div><strong>{event.summary}</strong><Badge tone={event.event_type.startsWith("human.") ? "violet" : "neutral"}>{event.event_type.replaceAll(".", " ")}</Badge></div>
                    <span>{event.actor}{event.entity_id ? " · " + event.entity_id : ""}</span>
                    {event.details?.reason && <p>Reason: {event.details.reason}</p>}
                  </div>
                  <time>{formatDate(event.created_at)}</time>
                </article>
              );
            })}
          </div>
        ) : <EmptyState title="No events match these filters" description="Run a scenario or change the filter to inspect the local audit history." />}
      </Card>
    </>
  );
}
