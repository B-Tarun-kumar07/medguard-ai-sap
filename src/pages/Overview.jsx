import React from "react";
import {
  Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Activity, ArrowRight, ArrowUpRight, Boxes, Building2, CheckCircle2, Clock3,
  ShieldAlert, Truck,
} from "lucide-react";
import { Badge, Card, EmptyState, PageHeading, RiskBadge, StatCard, formatDate, formatDateOnly, fmt } from "../components";

function CoverageTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return <div className="chart-tooltip"><strong>{row.hospital_full || row.hospital}</strong><span>{row.days} days of stock</span></div>;
}

export default function Overview({ data, navigate }) {
  const summary = data.overview || {};
  const rows = summary.coverage_chart || [];
  const alerts = summary.recent_disruptions || [];
  const critical = summary.critical_positions || [];
  const aster = data.inventory.find((item) => item.hospital_id === "ASTR" && item.medicine_id === "NOREPI");
  const displayRows = rows.map((item) => ({
    ...item,
    hospital: ({ ASTR: "Aster", STMA: "St. Martha", LAKE: "Lakeside", NORTH: "Northstar", COAST: "Coastal" })[item.hospital_id] || item.hospital,
    hospital_full: data.hospitals.find((h) => h.id === item.hospital_id)?.name || item.hospital,
  }));

  return (
    <>
      <PageHeading
        eyebrow="NETWORK CONTROL TOWER"
        title="Good morning, team"
        description="A clear view of medicine coverage, disruption exposure, and decisions waiting for your review."
        actions={<button className="button button-primary" onClick={() => navigate("disruption")}><Activity size={16} />Simulate disruption <ArrowRight size={15} /></button>}
      />
      <div className="simulation-banner">
        <div className="banner-icon"><Activity size={18} /></div>
        <div className="banner-copy">
          <strong>Finale demo scenario</strong>
          <span>Aster General has two days of norepinephrine. Its regular supplier delivery can be delayed to day five.</span>
        </div>
        <div className="banner-tags"><Badge tone="warning" dot>Simulated</Badge><span>~3 days uncovered</span></div>
        <button className="text-button" onClick={() => navigate("disruption")}>Open scenario <ArrowRight size={15} /></button>
      </div>

      <Card className="shortage-panel" title={<>Shortage alerts <Badge tone={summary.shortage_alerts?.length ? "critical" : "good"} dot>{summary.shortage_alerts?.length || 0} to review</Badge></>} subtitle="Current quantity compared with each pharmacy’s safety minimum." action={<button className="button button-outline" onClick={()=>navigate("inventory")}>Open inventory <ArrowRight size={14}/></button>}>
        {summary.shortage_alerts?.length ? <div className="alert-list">{summary.shortage_alerts.map((alert,index)=><div className="alert-row" key={alert.hospital_name+alert.medicine_name+index}><span className="alert-marker alert-marker-red"><ShieldAlert size={15}/></span><span className="alert-row-main"><strong>{alert.medicine_name} · {alert.condition}</strong><small>{alert.hospital_name} · {fmt(alert.current_stock)} {alert.unit} remaining · safety minimum {fmt(alert.safety_stock)} · {alert.days_remaining ?? "—"} days</small></span><RiskBadge risk={alert.risk}/></div>)}</div> : <div className="watch-empty"><strong>No critical shortages</strong><p>Critical alerts appear here when stock coverage reaches the alert threshold.</p></div>}
      </Card>

      <div className="stat-grid">
        <StatCard label="Hospitals monitored" value={summary.hospitals_monitored} note="Across Karnataka demo network" icon={Building2} accent="blue" onClick={() => navigate("inventory")} />
        <StatCard label="Medicines at risk" value={summary.medicines_at_risk} note={summary.critical_inventory_positions + " critical inventory position(s)"} icon={ShieldAlert} accent="amber" onClick={() => navigate("inventory")} />
        <StatCard label="Active disruptions" value={summary.active_disruptions} note={summary.active_disruptions ? "Response workflow in progress" : "No event currently active"} icon={Activity} accent="red" onClick={() => navigate("disruption")} />
        <StatCard label="Pending approvals" value={summary.pending_approvals} note={summary.pending_approvals ? "Human decision required" : "No action waiting for review"} icon={CheckCircle2} accent="green" onClick={() => navigate("approvals")} />
        <StatCard label="Shipments moving" value={summary.shipments_active} note="Approved, dispatched, or delayed" icon={Truck} accent="violet" onClick={() => navigate("transportation")} />
      </div>

      {summary.expiry_alerts?.length > 0 && <Card title="Expiry watch" subtitle="Medicine records with sample expiry dates within 30 days."><div className="alert-list">{summary.expiry_alerts.map(item=><div className="alert-row" key={item.medicine_name}><span className="alert-marker alert-marker-amber"><Clock3 size={15}/></span><span className="alert-row-main"><strong>{item.medicine_name}</strong><small>Sample manufacture {formatDateOnly(item.manufacture_date)} · sample expiry {formatDateOnly(item.expiry_date)}</small></span><Badge tone="warning" dot>{item.locations} inventory locations</Badge></div>)}</div></Card>}

      <div className="dashboard-grid dashboard-grid-top">
        <Card className="chart-panel" title="Critical medicine coverage" subtitle="Norepinephrine days on hand by hospital">
          <div className="chart-legend"><span><i className="legend-dot legend-green" />Days of stock</span><span><i className="legend-dash" />Critical threshold · 3 days</span></div>
          <div className="coverage-chart">
            {displayRows.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={displayRows} margin={{ top: 8, right: 8, left: -15, bottom: 0 }}>
                  <CartesianGrid stroke="#e9ece7" vertical={false} />
                  <XAxis dataKey="hospital" tick={{ fill: "#737e79", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 10]} tick={{ fill: "#8a9490", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(n) => n + "d"} />
                  <Tooltip content={<CoverageTooltip />} cursor={{ fill: "#f2f5f1" }} />
                  <ReferenceLine y={3} stroke="#d88d2d" strokeDasharray="4 4" />
                  <Bar dataKey="days" radius={[5, 5, 0, 0]} barSize={37} fill="#3e8b73" />
                </BarChart>
              </ResponsiveContainer>
            ) : <EmptyState title="Coverage data unavailable" description="Start the local API to load the demo dataset." />}
          </div>
          <div className="chart-foot"><span>Lowest coverage</span><strong>{aster?.hospital_name || "Aster General Hospital"} · {aster?.days_remaining ?? 2} days</strong><button className="icon-link" onClick={() => navigate("inventory")}>View inventory <ArrowRight size={14} /></button></div>
        </Card>

        <Card className="alerts-panel" title="Disruption watch" subtitle="Events detected by the sensing agent" action={<button className="icon-link" onClick={() => navigate("disruption")}>View all <ArrowRight size={14} /></button>}>
          {alerts.length ? (
            <div className="alert-list">
              {alerts.slice(0, 4).map((item) => (
                <button key={item.id} className="alert-row" onClick={() => navigate("disruption")}>
                  <span className={"alert-marker " + (item.severity === "Critical" ? "alert-marker-red" : "alert-marker-amber")}><Activity size={15} /></span>
                  <span className="alert-row-main"><strong>{item.title}</strong><small>{item.hospital_name} · {item.medicine_name}</small><small><Clock3 size={12} />{formatDate(item.created_at)}</small></span>
                  <RiskBadge risk={item.severity} />
                </button>
              ))}
            </div>
          ) : (
            <div className="watch-empty">
              <span className="watch-empty-icon"><CheckCircle2 size={18} /></span>
              <strong>No active disruption</strong>
              <p>Run the finale scenario to see the sensing and response agents coordinate.</p>
              <button className="button button-outline" onClick={() => navigate("disruption")}>Open disruption center <ArrowRight size={14} /></button>
            </div>
          )}
        </Card>
      </div>

      <div className="dashboard-grid dashboard-grid-bottom">
        <Card title="Inventory positions to watch" subtitle="Sorted by shortest coverage">
          {critical.length ? (
            <div className="compact-table-wrap">
              <table className="compact-table">
                <thead><tr><th>Medicine</th><th>Hospital</th><th>Coverage</th><th>Risk</th></tr></thead>
                <tbody>{critical.slice(0, 4).map((item, i) => (
                  <tr key={i}>
                    <td><div className="medicine-cell"><span className="medicine-mini">{item.medicine_name?.slice(0, 1)}</span><strong>{item.medicine_name}</strong></div></td>
                    <td>{item.hospital_name}</td>
                    <td><strong className="coverage-number">{fmt(item.days_remaining, 1)} days</strong></td>
                    <td><RiskBadge risk="Critical" /></td>
                  </tr>
                ))}</tbody>
              </table>
              <button className="table-link" onClick={() => navigate("inventory")}>Open full inventory <ArrowRight size={14} /></button>
            </div>
          ) : <EmptyState title="No low-stock positions" description="Current stock is above the configured critical threshold." icon={Boxes} />}
        </Card>
        <Card className="network-card" title="Network snapshot" subtitle="Fictional demo supply chain">
          <div className="network-kpis">
            <div><span>Hospitals</span><strong>{summary.hospitals_monitored || 0}</strong><small>regional facilities</small></div>
            <div><span>Suppliers</span><strong>{data.suppliers?.length || 4}</strong><small>qualified in demo</small></div>
            <div><span>Inventory records</span><strong>{data.inventory?.length || 25}</strong><small>stock / demand pairs</small></div>
          </div>
          <div className="network-health"><span className="online-dot" /><span>All demo agents are ready</span><Badge tone="good">Local</Badge></div>
          <div className="network-note"><span>Planning horizon</span><strong>7 days</strong><span>Default risk thresholds</span><strong>3d critical · 7d watch</strong></div>
        </Card>
      </div>
    </>
  );
}
