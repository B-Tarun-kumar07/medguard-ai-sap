
import React, { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, ZoomControl, useMap } from "react-leaflet";
import L from "leaflet";
import { api } from "./api";
import "leaflet/dist/leaflet.css";

const CITY_COORDS = {
  Bengaluru: [12.9716, 77.5946],
  Mysuru: [12.2958, 76.6394],
  Mangaluru: [12.9141, 74.8560],
  Hyderabad: [17.3850, 78.4867],
  Coimbatore: [11.0168, 76.9558]
};

function makeIcon(emoji, color) {
  return L.divIcon({
    className: "shipment-map-marker",
    html: `<div style="background:${color};width:34px;height:34px;border:3px solid white;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:17px;box-shadow:0 2px 9px #0005">${emoji}</div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17]
  });
}

const originIcon = makeIcon("📦", "#2878c8");
const destinationIcon = makeIcon("🏥", "#23845d");
const vehicleIcon = makeIcon("🚚", "#d97706");

function FitRoute({ points }) {
  const map = useMap();

  useEffect(() => {
    if (points.length) {
      map.fitBounds(points, { padding: [45, 45], maxZoom: 10 });
    }
  }, [map, points]);

  return null;
}

function MapNavigation({ routePoints, driverPosition, locationIsFresh, followDriver, setFollowDriver }) {
  const map = useMap();

  useEffect(() => {
    if (!locationIsFresh || !driverPosition || !followDriver) return;
    if (map.getZoom() >= 13) map.panTo(driverPosition, { animate: true, duration: 0.7 });
    else map.flyTo(driverPosition, 14, { animate: true, duration: 0.8 });
  }, [map, driverPosition?.[0], driverPosition?.[1], locationIsFresh, followDriver]);

  function showRoute() {
    setFollowDriver(false);
    map.fitBounds(routePoints, { padding: [45, 45], maxZoom: 10 });
  }

  function showDriver() {
    if (!locationIsFresh || !driverPosition) return;
    setFollowDriver(true);
    map.flyTo(driverPosition, Math.max(map.getZoom(), 14), { animate: true, duration: 0.8 });
  }

  return (
    <div className="shipment-map-controls" aria-label="Map navigation">
      <button type="button" onClick={showRoute}>Full route</button>
      <button type="button" disabled={!locationIsFresh} onClick={showDriver}>Driver location</button>
      {locationIsFresh && (
        <button type="button" className={followDriver ? "is-following" : ""}
          aria-pressed={followDriver} onClick={() => setFollowDriver((value) => !value)}>
          {followDriver ? "Following driver" : "Follow driver"}
        </button>
      )}
    </div>
  );
}

export default function ShipmentMap({ item }) {
  const originCity =
    item.source_city ||
    (item.source_type === "supplier"
      ? item.source_label?.includes("Westline") ? "Mangaluru"
      : item.source_label?.includes("Central Pharma") ? "Hyderabad"
      : item.source_label?.includes("SouthCross") ? "Coimbatore"
      : "Bengaluru"
      : item.source_label?.includes("Lakeside") ? "Mysuru" : "Bengaluru");

  const destinationCity = item.destination_city || "Bengaluru";

  const start = CITY_COORDS[originCity] || CITY_COORDS.Bengaluru;
  const end = CITY_COORDS[destinationCity] || CITY_COORDS.Bengaluru;

  const [liveLocation, setLiveLocation] = useState(null);
  const [followDriver, setFollowDriver] = useState(true);

  useEffect(() => {
    let active = true;
    async function loadLocation() {
      try {
        const result = await api.tracking(item.id);
        if (active) setLiveLocation(result.tracking?.location || null);
      } catch { /* Map remains usable when the tracking API is temporarily unavailable. */ }
    }
    loadLocation();
    const timer = window.setInterval(loadLocation, 10000);
    return () => { active = false; window.clearInterval(timer); };
  }, [item.id]);

  const locationIsFresh = liveLocation?.recorded_at && (Date.now() - new Date(liveLocation.recorded_at).getTime() < 120000);

  const routePoints = [start, end];
  const driverPosition = locationIsFresh ? [liveLocation.latitude, liveLocation.longitude] : null;

  return (
    <div className="shipment-map-shell">
      <div className="shipment-map-heading">
        <div>
          <strong>Live shipment map</strong>
          <small>{originCity} → {destinationCity}</small>
        </div>
        <span className="simulated-pill">● {locationIsFresh ? "LIVE GPS" : "AWAITING GPS"}</span>
      </div>

      <MapContainer
        center={start}
        zoom={7}
        zoomControl={false}
        scrollWheelZoom={false}
        className="shipment-leaflet-map"
      >
        <ZoomControl position="topleft" />
        <MapNavigation routePoints={routePoints} driverPosition={driverPosition}
          locationIsFresh={locationIsFresh} followDriver={followDriver} setFollowDriver={setFollowDriver} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <FitRoute points={routePoints} />

        <Polyline
          positions={routePoints}
          pathOptions={{ color: "#2878c8", weight: 5, opacity: 0.8, dashArray: "9 8" }}
        />

        <Marker position={start} icon={originIcon}>
          <Popup>Origin: {item.source_label}</Popup>
        </Marker>

        <Marker position={end} icon={destinationIcon}>
          <Popup>Destination: {item.destination_name}</Popup>
        </Marker>

        {item.status === "In Transit" && locationIsFresh && (
          <Marker position={[liveLocation.latitude, liveLocation.longitude]} icon={vehicleIcon}>
            <Popup>{`Driver GPS · accuracy ${Math.round(liveLocation.accuracy_m || 0)} m · updated ${new Date(liveLocation.recorded_at).toLocaleTimeString()}`}</Popup>
          </Marker>
        )}
      </MapContainer>

      <div className="shipment-map-legend">
        <span>📦 Origin</span>
        <span>🚚 Driver location</span>
        <span>🏥 Destination</span>
      </div>
      <p className="shipment-map-note">
        {locationIsFresh
          ? `Live driver location · updated ${new Date(liveLocation.recorded_at).toLocaleString()}`
          : "City-level route. Live GPS appears after the driver starts sharing from their device."}
      </p>
    </div>
  );
}
