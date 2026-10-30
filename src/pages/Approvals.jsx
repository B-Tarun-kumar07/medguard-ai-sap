import React, { useState } from "react";
import { ArrowDownToLine, ArrowRight, Check, CheckCircle2, ClipboardCheck, RotateCcw, ShieldCheck, X } from "lucide-react";
import { api } from "../api";
import { Badge, Card, EmptyState, PageHeading, RiskBadge, fmt, formatDate } from "../components";

export default function Approvals({ data, run, reviewer, setReviewer, navigate }) {
  const pending = data.approvals.filter((item) => item.decision === "pending");
  const history = data.approvals.filter((item) => item.decision !== "pending");
  const [reasons, setReasons] = useState({});
  const [busyId, setBusyId] = useState("");

  async function decide(item, decision) {
    const defaults = {
      approve: "Approved for the simulated recovery plan.",
      reject: "Rejected after human review.",
      revision: "Please confirm the route and stock balance before approval.",
    };
    const reason = (reasons[item.approval_id] || defaults[decision] || "").trim();
    setBusyId(item.approval_id);
    await run(
      () => api.decide(item.approval_id, { decision, reviewer, reason }),
      decision === "approve" ? "Approved. A shipment is now waiting to be dispatched." :
        decision === "reject" ? "Decision recorded. No shipment was created." : "Revision request logged.",
    );
    setBusyId("");
  }

  return (
    <>
      <PageHeading eyebrow="CONTROLLED EXECUTION" title="Approval center" description="Review every proposed transfer or purchase. Nothing moves until a named reviewer records a decision."
        actions={<button className="button button-outline" onClick={() => navigate("audit")}>Open audit trail <ArrowRight size={14} /></button>} />
      <div className="approval-policy"><span className="policy-icon"><ShieldCheck size={17} /></span><span><strong>Human-in-the-loop safeguard is active</strong><small>Approve creates an authorized shipment; dispatch and delivery remain separate tracked steps.</small></span><Badge tone="good">Enforced</Badge></div>
      <div className="reviewer-strip">
        <label><span>Reviewer name</span><input value={reviewer} onChange={(event) => setReviewer(event.target.value)} placeholder="Enter authorized reviewer" /></label>
        <div className="reviewer-count"><ClipboardCheck size={17} /><strong>{pending.length}</strong><span>pending decision{pending.length === 1 ? "" : "s"}</span></div>
      </div>

      <div className="approval-list">
        {pending.length ? pending.map((item) => (
          <Card className="approval-card" key={item.approval_id}>
            <div className="approval-card-head">
              <div className="approval-heading-icon"><ArrowDownToLine size={17} /></div>
              <div className="approval-heading-copy">
                <div className="approval-title-row"><h2>{item.recommendation_type === "transfer" ? "Inter-hospital stock transfer" : "Alternative supplier purchase"}</h2><Badge tone="warning" dot>Pending review</Badge></div>
                <p>{item.medicine_name} · {item.hospital_name}</p>
              </div>
              <div className="approval-quantity"><strong>{fmt(item.quantity)}</strong><span>{item.unit}</span></div>
            </div>
            <div className="approval-route">
              <div><small>Source</small><strong>{item.donor_hospital_name || item.supplier_name}</strong><span>{item.recommendation_type === "transfer" ? "Hospital stock" : "Supplier quote"}</span></div>
              <ArrowRight size={17} />
              <div><small>Destination</small><strong>{item.hospital_name}</strong><span>{item.medicine_name}</span></div>
              <div className="approval-eta"><small>Simulated arrival</small><strong>{item.details?.selected_route?.eta_hours ? fmt(item.details.selected_route.eta_hours, 1) + " hours" : fmt(item.details?.lead_days, 1) + " days"}</strong><span>{item.details?.selected_route?.name || "Route pending"}</span></div>
            </div>
            <div className="approval-evidence">
              <div className="evidence-reason"><span>Recommendation reasoning</span><p>{item.reason}</p></div>
              <div className="evidence-checks">
                {item.recommendation_type === "transfer" ? (
                  <>
                    <div className={item.details?.donor_safety_check ? "evidence-pass" : "evidence-warn"}><ShieldCheck size={15} /><span><strong>{item.details?.donor_safety_check ? "Donor safety stock protected" : "Safety check requires review"}</strong><small>{fmt(item.details?.donor_stock_after)} remaining vs {fmt(item.details?.donor_safety_stock)} minimum</small></span></div>
                    <div className="evidence-neutral"><CheckCircle2 size={15} /><span><strong>Medicine match checked</strong><small>Same medicine identifier and unit</small></span></div>
                  </>
                ) : (
                  <>
                    <div className="evidence-neutral"><CheckCircle2 size={15} /><span><strong>Supplier availability</strong><small>{fmt(item.details?.available_qty)} units on simulated offer</small></span></div>
                    <div className="evidence-neutral"><CheckCircle2 size={15} /><span><strong>Quote estimate</strong><small>USD {fmt(item.details?.estimated_cost, 2)} total · not a live quote</small></span></div>
                  </>
                )}
              </div>
            </div>
            <div className="approval-benefit"><CheckCircle2 size={15} /><span>{item.benefit}</span></div>
            <div className="approval-risk"><strong>Risk / limitation</strong><span>{item.risk}</span></div>
            <label className="decision-reason">
              <span>Decision reason <small>Added to the audit log</small></span>
              <textarea value={reasons[item.approval_id] || ""} onChange={(event) => setReasons({ ...reasons, [item.approval_id]: event.target.value })} placeholder="Add context for the decision (optional; a default reason is recorded if blank)." rows={2} />
            </label>
            <div className="decision-actions">
              <button className="button button-primary" disabled={busyId === item.approval_id || reviewer.trim().length < 2} onClick={() => decide(item, "approve")}>
                {busyId === item.approval_id ? <span className="spinner spinner-light" /> : <Check size={15} />}Approve action
              </button>
              <button className="button button-danger-outline" disabled={busyId === item.approval_id} onClick={() => decide(item, "reject")}><X size={15} />Reject</button>
              <button className="button button-quiet" disabled={busyId === item.approval_id} onClick={() => decide(item, "revision")}><RotateCcw size={15} />Request revision</button>
            </div>
          </Card>
        )) : (
          <Card><EmptyState title="Nothing waiting for approval" description="When the agents propose a transfer or procurement action, it will appear here for a named reviewer." icon={ClipboardCheck} action={<button className="button button-outline" onClick={() => navigate("disruption")}>Run a scenario</button>} /></Card>
        )}
      </div>

      <Card title="Decision history" subtitle="Reviewer, timestamp, outcome, and reason are retained for each action.">
        {history.length ? (
          <div className="table-scroll"><table className="data-table">
            <thead><tr><th>Decision</th><th>Action</th><th>Hospital</th><th>Reviewer</th><th>Recorded</th><th>Reason</th></tr></thead>
            <tbody>{history.map((item) => (
              <tr key={item.approval_id}>
                <td><RiskBadge risk={item.decision === "approve" ? "Approved" : item.decision === "reject" ? "Rejected" : "Revision Requested"} /></td>
                <td>{item.recommendation_type === "transfer" ? "Transfer" : "Procurement"} · {fmt(item.quantity)} {item.unit}</td>
                <td>{item.hospital_name}</td><td>{item.reviewer}</td><td>{formatDate(item.reviewed_at)}</td><td>{item.decision_reason}</td>
              </tr>
            ))}</tbody>
          </table></div>
        ) : <div className="history-empty"><span>No decisions recorded yet.</span><span>Approvals are preserved in the audit trail.</span></div>}
      </Card>
    </>
  );
}
