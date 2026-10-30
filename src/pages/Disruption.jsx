import React, { useState } from "react";
import { AlertTriangle, ArrowRight, Check, Circle, Clock3, Play, RotateCcw, ShieldCheck, Sparkles } from "lucide-react";
import { api } from "../api";
import { Badge, Card, EmptyState, PageHeading, RiskBadge, fmt, formatDate } from "../components";

const scenarios = [
  { id: "supplier_delay", title: "Supplier delivery delay", detail: "Core finale run: Aster’s regular supplier is delayed and delivery is expected on day five.", tag: "Finale scenario" },
  { id: "supplier_failure", title: "Supplier unavailable", detail: "Supplier failure with a seven-day fallback planning horizon, clearly marked uncertain.", tag: "Stress test" },
  { id: "demand_spike", title: "Demand spike", detail: "Aster’s daily norepinephrine demand increases by 50% for the simulated scenario.", tag: "Stress test" },
];

function AgentStep({ item, index }) {
  const waiting = item.status === "Awaiting review";
  return (
    <div className={"agent-step " + (waiting ? "agent-step-waiting" : "")}>
      <div className="step-node">{waiting ? <Clock3 size={15} /> : <Check size={15} />}</div>
      <div className="step-content"><strong>{item.agent}</strong><span>{item.summary}</span></div>
      <Badge tone={waiting ? "warning" : "good"}>{waiting ? "Awaiting review" : "Complete"}</Badge>
    </div>
  );
}

export default function Disruption({ data, run, navigate }) {
  const [scenario, setScenario] = useState("supplier_delay");
  const [busy, setBusy] = useState(false);
  const workflow = data.workflow || {};
  const event = workflow.disruption;
  const plan = workflow.planning || {};
  const inventory = workflow.inventory || {};
  const active = workflow.active && event;
  const selected = scenarios.find((item) => item.id === scenario);

  async function start() {
    setBusy(true);
    await run(() => api.simulate(scenario), "Agent workflow completed. Proposed actions are waiting for approval.");
    setBusy(false);
  }

  return (
    <>
      <PageHeading eyebrow="SENSE · PLAN · RECOVER" title="Disruption center" description="Trigger a fictional supply event and watch the specialized agents build a reviewable response." />
      <div className="scenario-layout">
        <Card className="scenario-launch-card" title="Simulate a disruption" subtitle="Choose an event. The agents will use the local inventory and supplier dataset.">
          <div className="scenario-options">
            {scenarios.map((item) => (
              <button key={item.id} className={"scenario-option " + (scenario === item.id ? "scenario-selected" : "")} onClick={() => setScenario(item.id)} disabled={!!active}>
                <span className="radio-indicator">{scenario === item.id && <i />}</span>
                <span className="scenario-option-copy"><strong>{item.title}</strong><small>{item.detail}</small></span>
                <span className={"scenario-tag " + (item.id === "supplier_delay" ? "scenario-tag-green" : "")}>{item.tag}</span>
              </button>
            ))}
          </div>
          <div className="scenario-target">
            <div className="scenario-target-icon"><AlertTriangle size={18} /></div>
            <div><strong>Target stock position</strong><span>Aster General · Norepinephrine 4 mg / 4 mL</span></div>
            <div className="target-days"><b>{data.inventory.find((item) => item.hospital_id === "ASTR" && item.medicine_id === "NOREPI")?.days_remaining ?? 2}</b><small>days left</small></div>
          </div>
          <div className="scenario-launch-foot">
            <span><span className="simulation-dot" />All values are deterministic demo data</span>
            <button className="button button-primary" onClick={start} disabled={busy || !!active}>
              {busy ? <span className="spinner spinner-light" /> : <Play size={15} fill="currentColor" />}
              {busy ? "Running agents…" : active ? "Disruption active" : "Run agent workflow"}
            </button>
          </div>
          {active && <div className="inline-hint"><RotateCcw size={14} />Use <strong>Reset demo</strong> in the top bar before running another scenario.</div>}
        </Card>

        <Card className="workflow-side" title="Agent sequence" subtitle="Five agents, one governed workflow">
          <div className="workflow-sequence">
            {["Sensing","Planning","Inventory","Logistics","Human review"].map((label, index) => (
              <div className="sequence-row" key={label}>
                <span className={"sequence-number " + (active ? "sequence-done" : "")}>{active ? <Check size={13} /> : String(index + 1).padStart(2, "0")}</span>
                <span>{label}</span>
                {index < 4 && <i className={active ? "sequence-line-done" : ""} />}
              </div>
            ))}
          </div>
          <div className="safety-note"><ShieldCheck size={17} /><span><strong>Human approval required</strong><small>Transfers and procurement remain proposals until an authorized reviewer decides.</small></span></div>
          <div className="workflow-mode"><Sparkles size={14} /><span>Deterministic calculations</span><Badge tone="neutral">No API key</Badge></div>
        </Card>
      </div>

      {active ? (
        <div className="response-section">
          <div className="response-heading">
            <div><div className="eyebrow">COORDINATED RESPONSE</div><h2>{event.title}</h2><p>{event.summary}</p></div>
            <div className="response-status"><RiskBadge risk={event.severity} /><span>{formatDate(event.created_at)}</span></div>
          </div>
          <div className="event-context">
            <div><span>Detected supplier</span><strong>{event.details?.supplier_name || "Deccan MedSupply"}</strong><small>{event.details?.supplier_status || "Delayed"}</small></div>
            <div><span>Medicine</span><strong>{event.medicine_name}</strong><small>{event.hospital_name}</small></div>
            <div><span>Stock now</span><strong>{fmt(event.details?.current_stock)} ampoules</strong><small>{fmt(event.details?.daily_demand)} used per day</small></div>
            <div><span>Expected arrival</span><strong>{fmt(event.impact_days)} days</strong><small>{plan.uncertain ? "Fallback estimate · uncertain" : "Simulated supplier ETA"}</small></div>
          </div>

          <div className="dashboard-grid response-grid">
            <Card title="Agent hand-offs" subtitle="Every agent action is recorded in the audit trail">
              <div className="agent-timeline">{workflow.agent_steps?.map((item, i) => <AgentStep item={item} index={i} key={item.agent + i} />)}</div>
            </Card>
            <Card title="Shortage exposure" subtitle={plan.formula || "Coverage = stock ÷ daily demand"}>
              {plan.shortage_hospitals?.length ? (
                <div className="exposure-list">
                  {plan.shortage_hospitals.map((item) => (
                    <div className="exposure-row" key={item.hospital_id}>
                      <span className="exposure-mark"><AlertTriangle size={14} /></span>
                      <span><strong>{item.hospital_name}</strong><small>Estimated {fmt(item.uncovered_quantity)} units uncovered by arrival</small></span>
                      <span className="exposure-days"><b>{fmt(item.days_remaining, 1)}</b><small>days</small></span>
                    </div>
                  ))}
                  <div className="exposure-foot"><span>Estimated shortage dates use current stock / demand.</span><span>{plan.uncertain ? "Uncertain horizon" : "Fictional estimate"}</span></div>
                </div>
              ) : <EmptyState title="No projected stockout in this horizon" description="The scenario did not create a positive coverage gap." />}
            </Card>
          </div>

          <Card className="handoff-card" title="Next step: human review" subtitle="Agent proposals are ready. No stock moved and no purchase was placed automatically." action={<button className="button button-outline" onClick={() => navigate("approvals")}>Review proposals <ArrowRight size={14} /></button>}>
            <div className="handoff-stats">
              <div><span>Transfer proposals</span><strong>{inventory.recommendations?.length || 0}</strong></div>
              <div><span>Alternative suppliers</span><strong>{inventory.supplier_options?.length || 0}</strong></div>
              <div><span>Safety-stock checks</span><strong>{inventory.checks?.safety_stock_enforced ? "Passed" : "Review required"}</strong></div>
              <div><span>Open approvals</span><strong>{data.overview?.pending_approvals || 0}</strong></div>
            </div>
            {workflow.narrative && <p className="llm-note"><Sparkles size={14} />Optional Ollama summary: {workflow.narrative}</p>}
          </Card>
        </div>
      ) : (
        <Card className="disruption-empty"><EmptyState title="No disruption has been simulated" description="Start with the supplier delay scenario to follow the finale story from early signal through human approval and recovery." icon={Circle} action={<button className="button button-outline" onClick={() => setScenario("supplier_delay")}>Use finale scenario</button>} /></Card>
      )}
    </>
  );
}
