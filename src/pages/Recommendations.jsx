import React from "react";
import { ArrowRight, CheckCircle2, CircleDollarSign, Clock3, PackageCheck, Plus, ShieldCheck, Truck } from "lucide-react";
import { api } from "../api";
import { Badge, Card, EmptyState, PageHeading, RiskBadge, fmt } from "../components";

export default function Recommendations({ data, run, navigate }) {
  const workflow = data.workflow || {};
  const options = workflow.inventory?.supplier_options || [];
  const current = data.recommendations.filter((item) => item.disruption_id === workflow.disruption?.id);
  const transferCount = current.filter((item) => item.recommendation_type === "transfer").length;
  const canRequest = workflow.disruption?.status === "active";

  async function requestSupplier(id) {
    await run(() => api.procure(id), "Procurement proposal queued for human approval.");
  }

  return (
    <>
      <PageHeading eyebrow="DECISION SUPPORT" title="AI recommendations" description="Review the transfer math, supplier alternatives, transport fit, and the limitations behind each proposal."
        actions={<button className="button button-outline" onClick={() => navigate("approvals")}>Approval center <ArrowRight size={15} /></button>} />
      <div className="recommendation-intro">
        <div className="recommendation-intro-icon"><PackageCheck size={20} /></div>
        <div><strong>{workflow.disruption?.title || "Recommendations appear after a scenario runs"}</strong>
          <p>{workflow.disruption?.summary || "Run the deterministic finale scenario to calculate hospital coverage, supplier options, and feasible transfers."}</p>
        </div>
        {workflow.disruption && <Badge tone={workflow.disruption.status === "recovered" ? "good" : "warning"} dot>{workflow.disruption.status === "recovered" ? "Recovered" : "Active event"}</Badge>}
      </div>

      <div className="dashboard-grid recommendation-grid">
        <Card title="Proposed stock transfers" subtitle="Transfer quantities preserve donor minimum safety stock.">
          {transferCount ? (
            <div className="recommendation-list">
              {current.filter((item) => item.recommendation_type === "transfer").map((item) => (
                <article className="recommendation-card" key={item.id}>
                  <div className="recommendation-card-top">
                    <div className="medicine-icon-box"><PackageCheck size={17} /></div>
                    <div className="recommendation-title"><strong>{fmt(item.quantity)} {item.unit} · {item.medicine_name}</strong><span>{item.donor_hospital_name} <ArrowRight size={13} /> {item.hospital_name}</span></div>
                    <RiskBadge risk={item.status} />
                  </div>
                  <p className="recommendation-reason">{item.reason}</p>
                  <div className="calculation-strip">
                    <div><span>Recipient gap</span><strong>{fmt(item.details?.coverage_gap)} {item.unit}</strong></div>
                    <div><span>Donor after transfer</span><strong>{fmt(item.details?.donor_stock_after)} {item.unit}</strong></div>
                    <div><span>Minimum to retain</span><strong>{fmt(item.details?.donor_safety_stock)} {item.unit}</strong></div>
                    <div className="check-pass"><ShieldCheck size={15} /><strong>{item.details?.donor_safety_check ? "Safety check passed" : "Check required"}</strong></div>
                  </div>
                  <div className="recommendation-bottom">
                    <span className="benefit-text"><CheckCircle2 size={15} />{item.benefit}</span>
                    {item.details?.selected_route && <span className="route-mini"><Truck size={14} />{item.details.selected_route.name} · {fmt(item.details.selected_route.eta_hours, 1)}h · {fmt(item.details.selected_route.distance_km)} km</span>}
                  </div>
                  <div className="limitation-line"><span>Risk / limitation</span>{item.risk}</div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="No transfer proposal yet" description="Run a supplier-delay or demand-spike scenario to calculate eligible donor stock." icon={PackageCheck} />
          )}
        </Card>

        <Card title="Alternative suppliers" subtitle="Live availability and price are not connected; these are fictional quote options.">
          {options.length ? (
            <div className="supplier-option-list">
              {options.map((supplier) => (
                <div className="supplier-option" key={supplier.supplier_id}>
                  <div className="supplier-option-head">
                    <span className="supplier-avatar">{supplier.supplier_name.slice(0, 1)}</span>
                    <div className="supplier-option-name"><strong>{supplier.supplier_name}</strong><small>{supplier.city} · reliability score {fmt(supplier.reliability)}%</small></div>
                    <Badge tone="good">Available</Badge>
                  </div>
                  <div className="supplier-metrics">
                    <div><span>Available</span><strong>{fmt(supplier.available_qty)} units</strong></div>
                    <div><span>Lead time</span><strong>{fmt(supplier.lead_days, 1)} days</strong></div>
                    <div><span>Quote</span><strong>USD {fmt(supplier.unit_price, 2)} / unit</strong></div>
                  </div>
                  <div className="supplier-reason"><Clock3 size={13} />{supplier.reason}</div>
                  <button className="button button-outline button-full" disabled={!canRequest} onClick={() => requestSupplier(supplier.supplier_id)}>
                    <Plus size={14} />Request replenishment approval
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="Supplier options will appear here" description="The inventory agent checks fictional supplier availability for the selected medicine." icon={CircleDollarSign} />
          )}
          <div className="panel-footnote"><ShieldCheck size={14} />A supplier quote creates a pending request only; it does not place an order.</div>
        </Card>
      </div>

      <Card title="Recommendation history" subtitle="All proposed actions and their recorded decision states">
        {current.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>Action</th><th>Destination</th><th>Source</th><th>Quantity</th><th>Status</th><th>Decision detail</th></tr></thead>
              <tbody>{current.map((item) => (
                <tr key={item.id}>
                  <td><strong>{item.recommendation_type === "transfer" ? "Inter-hospital transfer" : "Alternative procurement"}</strong><small>{item.medicine_name}</small></td>
                  <td>{item.hospital_name}</td>
                  <td>{item.donor_hospital_name || item.supplier_name || "—"}</td>
                  <td>{fmt(item.quantity)} {item.unit}</td>
                  <td><RiskBadge risk={item.status} /></td>
                  <td>{item.decision_reason || (item.status === "Pending approval" ? "Awaiting reviewer" : "Recorded in audit")}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <EmptyState title="No recommendation history" description="Run a scenario to create reviewable proposals." />}
      </Card>
    </>
  );
}
