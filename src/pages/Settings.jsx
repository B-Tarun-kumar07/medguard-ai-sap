import React, { useEffect, useState } from "react";
import { BookOpen, Check, CircleHelp, CloudCog, Database, ExternalLink, RefreshCw, Save, ServerCog, Settings2, ShieldCheck, Sparkles } from "lucide-react";
import { Button as FioriButton, MessageStrip, ObjectStatus } from "@ui5/webcomponents-react";
import { api } from "../api";
import { Badge, Card, PageHeading } from "../components";

const defaultSettings = {
  critical_days: 3, warning_days: 7, llm_provider: "deterministic",
  ollama_base_url: "http://localhost:11434", ollama_model: "llama3.2",
};

const sapSystems = [
  { name: "SAP IBP", area: "Demand and inventory planning", adapter: "Map forecasts and inventory targets to a future planning-service adapter.", icon: Database },
  { name: "SAP Ariba", area: "Supplier sourcing and quotes", adapter: "Replace the fictional supplier catalog with documented sourcing interfaces.", icon: CloudCog },
  { name: "SAP Transportation Management", area: "Freight, routes, and execution", adapter: "Connect route plans and shipment milestones through a documented transport interface.", icon: ServerCog },
  { name: "SAP Joule / AI services", area: "Agent orchestration", adapter: "Keep deterministic calculations; route optional narrative summaries to an authorized AI service.", icon: Sparkles },
];

export default function Settings({ data, run }) {
  const [adminKey, setAdminKey] = useState("");
  const [reportMessage, setReportMessage] = useState("");
  const [form, setForm] = useState(defaultSettings);
  const [provider, setProvider] = useState(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState("");
  const [sapIntegration, setSapIntegration] = useState(null);
  const [sapHana, setSapHana] = useState(null);
  const [sapBpa, setSapBpa] = useState(null);
  const [hanaCheck, setHanaCheck] = useState(null);
  const [checkingHana, setCheckingHana] = useState(false);
  const [hanaOutbox, setHanaOutbox] = useState(null);
  const [retryingHana, setRetryingHana] = useState(false);
  const [hanaRetryMessage, setHanaRetryMessage] = useState("");
  useEffect(() => { if (data.settings) setForm(data.settings); }, [data.settings]);
  useEffect(() => {
    api.sapIntegrationStatus().then((status) => {
      setSapIntegration(status.integration_suite);
      setSapHana(status.hana);
      setSapBpa(status.build_process_automation);
    }).catch(() => { setSapIntegration(null); setSapHana(null); setSapBpa(null); });
    api.hanaOutbox().then(setHanaOutbox).catch(() => setHanaOutbox(null));
  }, []);

  function update(key, value) { setForm((current) => ({ ...current, [key]: value })); }

  async function save() {
    await run(() => api.saveSettings({
      ...form,
      critical_days: Number(form.critical_days),
      warning_days: Number(form.warning_days),
    }), "System settings saved.");
  }

  async function downloadReport() {
    setReportMessage("");
    try {
      const response = await fetch("/api/admin/stock-sales.xlsx", { headers: { "X-Admin-Key": adminKey } });
      if (!response.ok) { const body = await response.json(); throw new Error(body.detail || "Admin report could not be downloaded."); }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a"); link.href = url; link.download = "medguard_admin_stock_sales.xlsx"; link.click(); URL.revokeObjectURL(url);
      setReportMessage("Admin workbook downloaded.");
    } catch (error) { setReportMessage(error.message); }
  }

  async function check() {
    setChecking(true);
    setCheckError("");
    try { setProvider(await api.checkProvider()); }
    catch (error) { setCheckError(error.message || "Could not check the provider."); }
    finally { setChecking(false); }
  }

  async function checkHana() {
    setCheckingHana(true);
    setHanaCheck(null);
    try {
      setHanaCheck(await api.checkSapHana());
      setHanaOutbox(await api.hanaOutbox());
    }
    catch (error) { setHanaCheck({ connected: false, message: error.message || "Could not check SAP HANA." }); }
    finally { setCheckingHana(false); }
  }

  async function retryHana() {
    setRetryingHana(true);
    setHanaRetryMessage("");
    try {
      const result = await api.retryHanaOutbox();
      setHanaOutbox(result);
      setHanaRetryMessage(result.sent_now
        ? `Sent ${result.sent_now} queued event${result.sent_now === 1 ? "" : "s"} to HANA.`
        : result.pending ? "HANA is still unreachable; queued events remain saved locally." : "No pending shipment events.");
    } catch (error) { setHanaRetryMessage(error.message || "Could not retry HANA events."); }
    finally { setRetryingHana(false); }
  }

  return (
    <>
      <PageHeading eyebrow="DEMO CONFIGURATION" title="System settings" description="Tune alert thresholds and inspect the optional local AI adapter. No secret is stored in the browser." />
      <div className="settings-layout">
        <Card title="Admin stock and sales report" subtitle="The server only returns this workbook when the configured admin key is supplied.">
          <label className="form-field"><span>Admin key</span><input type="password" value={adminKey} onChange={event=>setAdminKey(event.target.value)} placeholder="Enter admin key" autoComplete="off" /></label>
          <div className="settings-actions"><small>Workbook includes recorded sales and current demo stock. Only the configured server admin key can download it.</small><button className="button button-primary" onClick={downloadReport} disabled={!adminKey}>Download Excel</button></div>
          <p className="provider-limit"><CircleHelp size={14} />This shared key is a prototype gate, not separate user accounts or admin roles. Do not use it to protect production data.</p>
          {reportMessage && <div className="settings-error" role="status">{reportMessage}</div>}
        </Card>
        <Card title="Risk thresholds" subtitle="Days of stock are calculated as current usable stock divided by daily demand.">
          <div className="settings-form-grid">
            <label className="form-field"><span>Critical when coverage is at or below</span><div className="input-with-suffix"><input type="number" min="1" max="30" value={form.critical_days} onChange={(event) => update("critical_days", event.target.value)} /><span>days</span></div><small>Used for the critical inventory alert count.</small></label>
            <label className="form-field"><span>Watch when coverage is at or below</span><div className="input-with-suffix"><input type="number" min="2" max="90" value={form.warning_days} onChange={(event) => update("warning_days", event.target.value)} /><span>days</span></div><small>Must be greater than the critical threshold.</small></label>
          </div>
          <div className="threshold-preview"><span><i className="risk-dot risk-red" />Critical</span><span><i className="risk-dot risk-amber" />Watch</span><span><i className="risk-dot risk-green" />Healthy</span><small>Changes are saved to local SQLite and immediately affect risk labels.</small></div>
          <div className="settings-actions"><span className="settings-saved"><Database size={14} />Stored locally in this demo</span><button className="button button-primary" onClick={save}><Save size={15} />Save settings</button></div>
        </Card>

        <Card className="provider-card" title="AI provider" subtitle="The workflow works without API keys or internet access.">
          <label className="form-field"><span>Response explanation provider</span>
            <select className="wide-select" value={form.llm_provider} onChange={(event) => update("llm_provider", event.target.value)}>
              <option value="deterministic">Deterministic local agent (default)</option>
              <option value="ollama">Local Ollama (optional)</option>
            </select>
          </label>
          {form.llm_provider === "ollama" ? (
            <div className="ollama-fields">
              <label className="form-field"><span>Ollama base URL</span><input value={form.ollama_base_url} onChange={(event) => update("ollama_base_url", event.target.value)} placeholder="http://localhost:11434" /></label>
              <label className="form-field"><span>Local model name</span><input value={form.ollama_model} onChange={(event) => update("ollama_model", event.target.value)} placeholder="llama3.2" /></label>
            </div>
          ) : <div className="deterministic-note"><ShieldCheck size={16} /><span><strong>Ready without a language model</strong><small>Agent calculations, recommendations, and audit events are generated locally from the demo data.</small></span></div>}
          <div className="provider-actions">
            <button className="button button-outline" onClick={check} disabled={checking}>{checking ? <span className="spinner" /> : <RefreshCw size={14} />}Check connection</button>
            <button className="button button-primary" onClick={save}><Save size={15} />Save provider</button>
          </div>
          {provider && <div className={"connection-result " + (provider.connected ? "connection-ok" : "connection-off")}><span className={provider.connected ? "online-dot" : "offline-dot"} /><span><strong>{provider.message}</strong>{provider.models?.length > 0 && <small>Available: {provider.models.join(", ")}</small>}</span></div>}
          {checkError && <div className="settings-error">{checkError}</div>}
          <p className="provider-limit"><CircleHelp size={14} />Ollama, when selected and reachable, provides narrative text only. It never sets inventory quantities or approves actions.</p>
        </Card>
      </div>

      <Card title="SAP Integration Suite" subtitle="Optional shipment-event integration through an SAP Integration Suite iFlow.">
        <div className={"connection-result " + (sapIntegration?.configured ? "connection-ok" : "connection-off")}>
          <ObjectStatus state={sapIntegration?.configured ? "Positive" : "Critical"} showDefaultIcon>
            {sapIntegration?.configured ? "Configuration complete" : "Not configured — local demo remains active"}
          </ObjectStatus>
          <span>
            <small>{sapIntegration?.configured
              ? "Shipment status changes will be sent to the configured Integration Suite endpoint."
              : "Set the SAP OAuth and iFlow endpoint variables on the backend to enable shipment events."}</small>
          </span>
        </div>
        {sapIntegration?.missing_settings?.length > 0 && <p className="provider-limit">Missing backend settings: {sapIntegration.missing_settings.join(", ")}</p>}
      </Card>

      <Card title="SAP Build Process Automation" subtitle="Optional workflow trigger when a hospital submits a medicine request.">
        <div className={"connection-result " + (sapBpa?.configured ? "connection-ok" : "connection-off")}>
          <ObjectStatus state={sapBpa?.configured ? "Positive" : "Critical"} showDefaultIcon>
            {sapBpa?.configured ? "Configuration complete" : "Not configured — local requests remain active"}
          </ObjectStatus>
          <span>
            <small>{sapBpa?.configured
              ? "New medicine requests will also start the configured SAP workflow. Local requests and approvals remain the source of truth."
              : "Configure the BPA service endpoint, OAuth client, and deployed workflow ID on the backend to enable workflow triggers."}</small>
          </span>
        </div>
        {sapBpa?.missing_settings?.length > 0 && <p className="provider-limit">Missing backend settings: {sapBpa.missing_settings.join(", ")}</p>}
        <p className="provider-limit"><CircleHelp size={14} />The SAP workflow is an optional approval process; it does not approve requests or change inventory by itself.</p>
      </Card>

      <Card title="SAP HANA Cloud" subtitle="Optional direct shipment-event log in your Hackfest HANA database.">
        <div className={"connection-result " + (sapHana?.configured ? "connection-ok" : "connection-off")}>
          <ObjectStatus state={sapHana?.configured ? "Positive" : "Critical"} showDefaultIcon>
            {sapHana?.configured ? "Credentials configured" : "Not configured — local demo remains active"}
          </ObjectStatus>
          <span>
            <small>{sapHana?.configured
              ? `Shipment status events will be written to the configured HANA endpoint on port ${sapHana.port}.`
              : "Set SAP_HANA_USER and SAP_HANA_PASSWORD on the backend. The connection uses encrypted TLS on port 443."}</small>
          </span>
        </div>
        {sapHana?.missing_settings?.length > 0 && <p className="provider-limit">Missing backend settings: {sapHana.missing_settings.join(", ")}</p>}
        <div className="provider-actions">
          <FioriButton design="Default" onClick={checkHana} disabled={checkingHana || !sapHana?.configured}>
            {checkingHana ? "Testing HANA…" : "Test HANA connection"}
          </FioriButton>
        </div>
        {hanaCheck && <div className="hana-message" role="status">
          <MessageStrip design={hanaCheck.connected ? "Positive" : "Negative"} hideCloseButton>
            <strong>{hanaCheck.connected ? "HANA connection successful. " : "HANA connection failed. "}</strong>{hanaCheck.message}
          </MessageStrip>
        </div>}
        <div className="hana-outbox">
          <div><strong>Shipment event delivery</strong><span><b>{hanaOutbox?.pending ?? sapHana?.outbox_pending ?? 0}</b> waiting · <b>{hanaOutbox?.sent ?? sapHana?.outbox_sent ?? 0}</b> sent to HANA</span></div>
          <FioriButton design="Default" onClick={retryHana} disabled={retryingHana || !((hanaOutbox?.pending ?? sapHana?.outbox_pending) > 0)}>
            {retryingHana ? "Retrying…" : "Retry pending events"}
          </FioriButton>
        </div>
        {hanaRetryMessage && <div className="settings-error" role="status">{hanaRetryMessage}</div>}
        <p className="provider-limit"><CircleHelp size={14} />Pending events stay in local SQLite and can be retried here. HANA uses a stable event ID so retries do not create duplicate rows. HANA errors never stop local shipment updates.</p>
      </Card>

      <Card title="Other SAP extension points" subtitle="Additional SAP products can be added as separate adapters when a tenant and API are available.">
        <div className="sap-adapter-grid">
          {sapSystems.map((item) => {
            const Icon = item.icon;
            return <div className="sap-adapter" key={item.name}><span className="sap-adapter-icon"><Icon size={17} /></span><div><div className="sap-adapter-title"><strong>{item.name}</strong><Badge tone="neutral">Planned adapter</Badge></div><span>{item.area}</span><p>{item.adapter}</p></div></div>;
          })}
        </div>
        <div className="sap-disclaimer"><ShieldCheck size={15} /><span>SAP IBP, SAP Ariba, SAP Transportation Management, and Joule remain planned adapters. Configured SAP shipment adapters forward status events only.</span></div>
      </Card>

      <Card title="Learning resources referenced" subtitle="Based on the Learning Assets page in the supplied Participant Guide.">
        <div className="learning-card">
          <BookOpen size={18} />
          <div><strong>SAP Learning Hub, student edition</strong>
            <p>The guide lists SAP BTP/CAP extension practice, SAP Build and Business Application Studio, SAP HANA Cloud modeling, SAP Analytics Cloud, SAP Business Data Cloud, and SAP Generative AI Hub prompt resources.</p>
            <small>Used in this prototype: the supplied participant guide’s Theme 1, Round 2 expectations, and learning-assets list. No Learning Hub course, hands-on system, or SAP tenant was accessed because organizer access was not provided.</small>
          </div>
          <Badge tone="warning">Access not provided</Badge>
        </div>
      </Card>
    </>
  );
}
