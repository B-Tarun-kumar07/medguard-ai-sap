"""Route options based only on the labeled fictional demo network."""

from __future__ import annotations

import json
import sqlite3

from backend.agents.inventory import city_distance
from backend.db import record_audit


def route_options(origin_city: str, destination_city: str, quantity: float) -> list[dict]:
    distance = city_distance(origin_city, destination_city)
    same_city = origin_city == destination_city
    road_eta = 2.0 if same_city else round(distance / 38 + 0.25, 1)
    road = {
        "name": "Medical van - " + ("city corridor" if same_city else "NH 275 / state highway"),
        "mode": "Temperature-controlled medical van",
        "distance_km": distance,
        "eta_hours": road_eta,
        "capacity": 120,
        "feasible": quantity <= 120,
        "status": "Available" if quantity <= 120 else "Insufficient capacity",
        "risk": "Standard simulated route",
        "simulated": True,
        "waypoints": [origin_city, "Regional transfer point", destination_city],
    }
    air_capacity = 40
    air_eta = 1.8 if same_city else round(max(1.5, distance / 210 + 0.7), 1)
    air = {
        "name": "Priority medical courier",
        "mode": "Priority air / final-mile courier",
        "distance_km": distance,
        "eta_hours": air_eta,
        "capacity": air_capacity,
        "feasible": quantity <= air_capacity,
        "status": "Available" if quantity <= air_capacity else "Insufficient capacity",
        "risk": "Small-batch option; simulated connection",
        "simulated": True,
        "waypoints": [origin_city, "Regional air hub", destination_city],
    }
    return [road, air]


def enrich_recommendations(connection: sqlite3.Connection, inventory_result: dict) -> dict:
    enriched = []
    for recommendation in inventory_result["recommendations"]:
        donor = connection.execute("SELECT city FROM hospitals WHERE id=?", (recommendation["donor_hospital_id"],)).fetchone()
        recipient = connection.execute("SELECT city FROM hospitals WHERE id=?", (recommendation["hospital_id"],)).fetchone()
        options = route_options(donor["city"], recipient["city"], recommendation["quantity"])
        feasible = [option for option in options if option["feasible"]]
        selected = min(feasible, key=lambda option: option["eta_hours"]) if feasible else None
        recommendation["route_options"] = options
        recommendation["selected_route"] = selected
        recommendation["route_warning"] = None if selected else "No simulated route can carry the proposed quantity."
        detail_row = connection.execute("SELECT details_json FROM recommendations WHERE id=?", (recommendation["id"],)).fetchone()
        details = json.loads(detail_row["details_json"])
        details.update({"route_options": options, "selected_route": selected})
        connection.execute("UPDATE recommendations SET details_json=? WHERE id=?", (json.dumps(details), recommendation["id"]))
        enriched.append(recommendation)
    inventory_result["recommendations"] = enriched
    record_audit(
        connection, "agent.logistics", "Logistics and Transportation Agent",
        "Compared simulated route time, capacity, and transport modes for the proposed stock transfers.",
        "disruption", enriched[0]["id"] if enriched else None,
        {"recommendation_count": len(enriched), "routes": [
            {"recommendation_id": item["id"], "options": item["route_options"], "selected": item["selected_route"]}
            for item in enriched
        ]},
    )
    return inventory_result
