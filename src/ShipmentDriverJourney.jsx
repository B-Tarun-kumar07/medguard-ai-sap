import React, { useEffect, useState } from "react";
import { api } from "./api";

const steps = [
  ["driver_assigned", "Driver assigned"],
  ["going_to_pickup", "Going to pickup"],
  ["picked_up", "Medicine picked up"],
  ["on_the_way", "On the way to hospital"],
  ["delivered", "Delivered"],
];

export default function ShipmentDriverJourney({ item, run }) {
  const [tracking, setTracking] = useState({});
  const [busy, setBusy] = useState(false);
  const [gpsSharing, setGpsSharing] = useState(false);
  const [gpsError, setGpsError] = useState("");

  async function refreshTracking() {
    try {
      const result = await api.tracking(item.id);
      setTracking(result.tracking || {});
    } catch (error) {
      console.error("Could not load tracking:", error);
    }
  }

  useEffect(() => {
    refreshTracking();
  }, [item.id]);

  useEffect(() => {
    if (!gpsSharing) return undefined;
    if (item.status !== "In Transit") {
      setGpsSharing(false);
      api.clearLocation(item.id).catch(() => {});
      return undefined;
    }
    if (!navigator.geolocation) return undefined;
    const watchId = navigator.geolocation.watchPosition(async (position) => {
      const coords = position.coords;
      try {
        const result = await api.updateLocation(item.id, {
          latitude: coords.latitude,
          longitude: coords.longitude,
          accuracy_m: coords.accuracy,
          speed_mps: coords.speed,
          heading_deg: coords.heading,
        });
        setTracking((current) => ({ ...current, location: result.location }));
        setGpsError("");
      } catch (error) {
        setGpsError(error.message || "Could not send GPS location.");
      }
    }, (error) => {
      setGpsError(error.code === 1 ? "Location permission was denied." : "Could not read the device location.");
      setGpsSharing(false);
    }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 });
    return () => navigator.geolocation.clearWatch(watchId);
  }, [gpsSharing, item.id, item.status]);

  const stage = tracking.stage || "";
  const stageIndex = steps.findIndex((step) => step[0] === stage);

  async function updateStage(nextStage) {
    if (busy) return;
    setBusy(true);

    try {
      await run(async () => {
        if (nextStage === "picked_up" && item.status === "Approved") {
          await api.advance(item.id, "Dispatched");
        }

        if (nextStage === "on_the_way" && item.status === "Dispatched") {
          await api.advance(item.id, "In Transit");
        }

        if (nextStage === "delivered") {
          if (item.status === "In Transit" || item.status === "Delayed") {
            await api.advance(item.id, "Delivered");
          } else {
            throw new Error("Shipment must be in transit before delivery.");
          }
        }

        await api.updateTracking(item.id, nextStage);
        await refreshTracking();
      }, "Driver journey updated successfully.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleGpsSharing() {
    setGpsError("");
    if (gpsSharing) {
      setGpsSharing(false);
      try { await api.clearLocation(item.id); }
      catch (error) { setGpsError(error.message || "Could not clear the shared location."); }
    } else if (!navigator.geolocation) {
      setGpsError("This browser does not support location sharing.");
    } else {
      setGpsSharing(true);
    }
  }

  const nextStep = steps[stageIndex + 1];

  return (
    <div style={{
      margin: "12px 14px",
      padding: 16,
      border: "1px solid #dce9e1",
      borderRadius: 14,
      background: "#f8fbf9"
    }}>
      <strong style={{ color: "#254b39", fontSize: 15 }}>
        🚚 Driver journey
      </strong>

      <div style={{ marginTop: 12, display: "grid", gap: 9 }}>
        {steps.map(([key, label], index) => {
          const complete = index <= stageIndex;

          return (
            <div key={key} style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              color: complete ? "#287a56" : "#929e96",
              fontSize: 12
            }}>
              <span style={{
                width: 21,
                height: 21,
                borderRadius: "50%",
                display: "grid",
                placeItems: "center",
                background: complete ? "#d9f1e3" : "#e9eeeb",
                fontWeight: 800
              }}>
                {complete ? "✓" : index + 1}
              </span>
              <span style={{ fontWeight: complete ? 700 : 400 }}>
                {label}
              </span>
            </div>
          );
        })}
      </div>

      {tracking.driver_name && (
        <div style={{
          marginTop: 14,
          padding: 12,
          background: "white",
          borderRadius: 10,
          fontSize: 12,
          color: "#52645b"
        }}>
          <strong>Driver:</strong> {tracking.driver_name}
          <br />
          <strong>Vehicle:</strong> {tracking.vehicle}
          <br />
          <strong>Vehicle number:</strong> {tracking.vehicle_number}
        </div>
      )}

      {tracking.traffic && (
        <div style={{
          marginTop: 10,
          padding: 12,
          background: "white",
          borderRadius: 10,
          fontSize: 12,
          color: "#52645b"
        }}>
          <strong>Traffic:</strong> {tracking.traffic}
          <br />
          <strong>Simulated ETA:</strong> {tracking.eta_minutes} minutes
        </div>
      )}

      {item.status === "In Transit" && (
        <div style={{ marginTop: 12 }}>
          <button className={gpsSharing ? "button button-outline" : "button button-primary"}
            onClick={toggleGpsSharing}>
            {gpsSharing ? "Stop sharing GPS" : "Start live GPS sharing"}
          </button>
          <p style={{ margin: "8px 0 0", color: "#849088", fontSize: 11 }}>
            {gpsSharing ? "This device is sharing its location with the shipment map." : "Start this on the driver’s device. Your browser will ask for location permission."}
          </p>
          {gpsError && <p role="alert" style={{ color: "#a33", fontSize: 11 }}>{gpsError}</p>}
        </div>
      )}

      <button
        className="button button-primary"
        style={{ marginTop: 14 }}
        disabled={busy || !nextStep || item.status === "Delivered"}
        onClick={() => updateStage(nextStep?.[0])}
      >
        {busy
          ? "Updating..."
          : stageIndex === -1
            ? "Assign driver"
            : nextStep
              ? nextStep[1]
              : "Journey complete"}
      </button>

      <p style={{
        margin: "10px 0 0",
        color: "#849088",
        fontSize: 10
      }}>
        Driver, vehicle, traffic and ETA are demo details. Live GPS is shared only while the driver enables it.
      </p>
    </div>
  );
}
