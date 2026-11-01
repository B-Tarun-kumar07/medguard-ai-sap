import React, { useEffect, useMemo, useState } from "react";
import { ArrowRightLeft, RefreshCw } from "lucide-react";
import { api } from "../api";
import { Badge, Card, EmptyState, fmt, formatDate } from "../components";

export default function HospitalRequests({ hospitalId, inventory, canWrite, run }) {
  const [requests, setRequests] = useState([]);
  const [donors, setDonors] = useState([]);
  const [busy, setBusy] = useState(false);
  const lowStock = useMemo(() => inventory.filter((item) => Number(item.current_stock) <= Number(item.reorder_point)), [inventory]);
  const [form, setForm] = useState({ medicine_id: "", donor_hospital_id: "", quantity: "", message: "" });

  useEffect(() => {
    if (!inventory.length) return;
    setForm((current) => {
      const medicineId = current.medicine_id && inventory.some((item) => item.medicine_id === current.medicine_id)
        ? current.medicine_id : (lowStock[0]?.medicine_id || inventory[0].medicine_id);
      const medicine = inventory.find((item) => item.medicine_id === medicineId);
      const suggested = Math.max(1, Math.ceil(Number(medicine?.reorder_point || 0) * 2 - Number(medicine?.current_stock || 0)));
      return { ...current, medicine_id: medicineId, quantity: current.quantity || String(suggested) };
    });
  }, [inventory, lowStock]);

  async function refresh() {
    if (!hospitalId) return;
    try { setRequests(await api.hospitalRequests(hospitalId)); }
    catch (error) { console.error("Could not load hospital requests:", error); }
  }

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 8000);
    return () => window.clearInterval(timer);
  }, [hospitalId]);

  useEffect(() => {
    if (!hospitalId || !form.medicine_id) return;
    let active = true;
    api.requestOptions(hospitalId, form.medicine_id, Math.max(1, Number(form.quantity) || 1)).then((result) => { if (active) setDonors(result); })
      .catch((error) => { if (active) console.error("Could not load donor hospitals:", error); });
    return () => { active = false; };
  }, [hospitalId, form.medicine_id, form.quantity]);

  const medicine = inventory.find((item) => item.medicine_id === form.medicine_id);
  const selectedDonor = donors.find((item) => item.hospital_id === form.donor_hospital_id);
  const bestMatch = donors.find((item) => item.can_fulfill);
  const outgoing = requests.filter((item) => item.requester_hospital_id === hospitalId);
  const incoming = requests.filter((item) => item.can_respond);

  async function submit(event) {
    event.preventDefault();
    if (!canWrite || busy) return;
    setBusy(true);
    try {
      const ok = await run(() => api.createHospitalRequest(hospitalId, {
        donor_hospital_id: form.donor_hospital_id || null,
        medicine_id: form.medicine_id,
        quantity: Number(form.quantity),
        message: form.message,
      }), form.donor_hospital_id ? "Request sent to the selected hospital." : "Request broadcast to all other hospitals.");
      if (ok) {
        setForm((current) => ({ ...current, donor_hospital_id: "", message: "" }));
        await refresh();
      }
    } finally { setBusy(false); }
  }

  async function respond(request, decision) {
    const ok = await run(() => api.decideHospitalRequest(hospitalId, request.id, { decision }),
      decision === "accept" ? "Request accepted. A hospital transfer shipment was created." : "Request declined.");
    if (ok) await refresh();
  }

  return (
    <div className="workspace-grid">
      <Card title="Request medicine from a hospital" subtitle="See which nearby hospitals can fulfill this quantity after protecting their safety stock.">
        {lowStock.length > 0 && <div className="auth-role-strip" style={{ marginBottom: 14 }}>
          <span><strong>{lowStock.length} low-stock item{lowStock.length === 1 ? "" : "s"}</strong> at or below reorder point</span>
          <Badge tone="warning">Review now</Badge>
        </div>}
        <form className="compact-form" onSubmit={submit}>
          <label>Medicine<select required value={form.medicine_id} onChange={(event) => {
            const selected = inventory.find((item) => item.medicine_id === event.target.value);
            const suggested = Math.max(1, Math.ceil(Number(selected?.reorder_point || 0) * 2 - Number(selected?.current_stock || 0)));
            setForm({ ...form, medicine_id: event.target.value, donor_hospital_id: "", quantity: String(suggested) });
          }}>
            {inventory.map((item) => <option key={item.medicine_id} value={item.medicine_id}>{item.medicine_name}{Number(item.current_stock) <= Number(item.reorder_point) ? " · LOW STOCK" : ""}</option>)}
          </select></label>
          <label>Send request to<select value={form.donor_hospital_id} onChange={(event) => setForm({ ...form, donor_hospital_id: event.target.value })}>
            <option value="">Any hospital (broadcast)</option>
            {donors.map((item) => <option key={item.hospital_id} value={item.hospital_id}>
              {item.recommended ? "Recommended - " : item.can_fulfill ? "Can fulfill - " : "Short by " + fmt(item.shortfall) + " - "}
              {item.hospital_name} · {item.city}{item.estimated_distance_km == null ? "" : " · ~" + item.estimated_distance_km + " km"} · {fmt(item.available_quantity)} available
            </option>)}
          </select></label>
          <label>Quantity ({medicine?.unit || "units"})<input type="number" min="1" step="1" required value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })}/></label>
          {medicine && <div className="auth-role-strip" style={{ margin: 0 }}>
            <span>Current stock <strong>{fmt(medicine.current_stock)}</strong> · reorder point <strong>{fmt(medicine.reorder_point)}</strong></span>
          </div>}
          {selectedDonor && <div className="auth-role-strip" style={{ margin: 0 }}>
            <span>{selectedDonor.can_fulfill ? <><strong>{selectedDonor.hospital_name}</strong> can fulfill this request with <strong>{fmt(selectedDonor.available_quantity)} {medicine?.unit}</strong> shareable above safety stock{selectedDonor.estimated_distance_km == null ? "." : ` · approximately ${selectedDonor.estimated_distance_km} km away.`}</> : <><strong>{selectedDonor.hospital_name}</strong> is short by <strong>{fmt(selectedDonor.shortfall)} {medicine?.unit}</strong>; another match or broadcast may work.</>}</span>
          </div>}
          {!selectedDonor && bestMatch && <div className="auth-role-strip" style={{ margin: 0 }}>
            <span>Best available match: <strong>{bestMatch.hospital_name}</strong> · {bestMatch.city} · <strong>{fmt(bestMatch.available_quantity)} {medicine?.unit}</strong> shareable{bestMatch.estimated_distance_km == null ? "" : ` · approximately ${bestMatch.estimated_distance_km} km away`}.</span>
            <button type="button" className="button button-outline" onClick={() => setForm((current) => ({ ...current, donor_hospital_id: bestMatch.hospital_id }))}>Choose match</button>
          </div>}
          {!selectedDonor && !bestMatch && donors.length > 0 && <div className="auth-role-strip" style={{ margin: 0 }}>
            <span>No single hospital can fulfill <strong>{fmt(form.quantity)} {medicine?.unit}</strong> while keeping its safety stock. You can broadcast the request for a donor to review what it can safely offer.</span>
          </div>}
          <label className="request-message">Message to hospitals<input maxLength="500" placeholder="Optional: explain the shortage or urgency" value={form.message} onChange={(event) => setForm({ ...form, message: event.target.value })}/></label>
          <button className="button button-primary" disabled={!canWrite || busy || !form.medicine_id || Number(form.quantity) < 1}>
            <ArrowRightLeft size={15}/>{busy ? "Sendingâ€¦" : form.donor_hospital_id ? "Send specific request" : "Broadcast request"}
          </button>
        </form>
      </Card>

      <Card title="Requests for this hospital" subtitle="Open requests from other hospitals appear here automatically.">
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10 }}>
          <button className="button button-outline" onClick={refresh}><RefreshCw size={14}/>Refresh</button>
        </div>
        {incoming.length ? <div className="alert-list">{incoming.map((item) => (
          <div className="alert-row" key={item.id} style={{ alignItems: "flex-start" }}>
            <span className="alert-marker alert-marker-amber"><ArrowRightLeft size={15}/></span>
            <span className="alert-row-main">
              <strong>{item.requester_name} needs {fmt(item.quantity)} {item.unit} of {item.medicine_name}</strong>
              <small>{item.is_open ? "Broadcast to any hospital" : `Addressed to ${item.donor_name}`}</small>
              {item.message && <small>{item.message}</small>}
              <small>{formatDate(item.created_at)}</small>
            </span>
            <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
              <button className="button button-primary" disabled={!canWrite} onClick={() => respond(item, "accept")}>Accept & transfer</button>
              {!item.is_open && <button className="button button-outline" disabled={!canWrite} onClick={() => respond(item, "decline")}>Decline</button>}
            </div>
          </div>
        ))}</div> : <EmptyState title="No incoming requests" description="Requests sent to this hospital or broadcast to all hospitals will appear here."/>}
      </Card>

      <Card title="Requests sent by this hospital" subtitle="Accepted requests create a shipment; declined or open requests stay in the request history.">
        {outgoing.length ? <div className="table-scroll"><table className="data-table">
          <thead><tr><th>Medicine</th><th>Quantity</th><th>Hospital</th><th>Status</th><th>Shipment</th><th>Requested</th></tr></thead>
          <tbody>{outgoing.map((item) => <tr key={item.id}>
            <td><strong>{item.medicine_name}</strong></td><td>{fmt(item.quantity)} {item.unit}</td>
            <td>{item.donor_name || (item.status === "accepted" ? "Matched hospital" : "Any available hospital")}</td>
            <td><Badge tone={item.status === "accepted" ? "good" : item.status === "declined" ? "warning" : "neutral"}>{item.status}</Badge></td>
            <td>{item.shipment_id || "â€”"}</td><td>{formatDate(item.created_at)}</td>
          </tr>)}</tbody>
        </table></div> : <EmptyState title="No requests sent yet" description="Use the form above when your stock needs support."/>}
      </Card>
    </div>
  );
}
