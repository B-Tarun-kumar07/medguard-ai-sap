"""Inventory allocation and supplier option agent with safety-stock checks."""

from __future__ import annotations

import json
import sqlite3
from math import isfinite

from backend.db import new_id, now_iso, record_audit

CITY_DISTANCE_KM = {
    ("Bengaluru", "Bengaluru"): 18,
    ("Bengaluru", "Mysuru"): 150,
    ("Mysuru", "Bengaluru"): 150,
    ("Bengaluru", "Mangaluru"): 350,
    ("Mangaluru", "Bengaluru"): 350,
    ("Mysuru", "Mangaluru"): 260,
    ("Mangaluru", "Mysuru"): 260,
}


def city_distance(origin: str, destination: str) -> int:
    return CITY_DISTANCE_KM.get((origin, destination), 280)


def transferable_surplus(current_stock: float, safety_stock: float, reserved: float = 0) -> int:
    values = (float(current_stock), float(safety_stock), float(reserved))
    if not all(isfinite(value) for value in values):
        return 0
    return max(0, int(values[0] - values[1] - values[2]))


def transfer_preserves_safety(current_stock: float, safety_stock: float, quantity: float) -> bool:
    if not all(isfinite(float(value)) for value in (current_stock, safety_stock, quantity)):
        return False
    return quantity > 0 and current_stock - quantity >= safety_stock


def plan_allocations(connection: sqlite3.Connection, disruption: dict, plan: dict) -> dict:
    affected = sorted(
        (row for row in plan["hospitals"] if row["affected"]),
        key=lambda row: row["days_remaining"] if row["days_remaining"] is not None else 999,
    )
    donor_rows = connection.execute(
        """SELECT h.id AS hospital_id,h.name AS hospital_name,h.city,
                  i.current_stock,i.daily_demand,i.safety_stock
           FROM inventory i JOIN hospitals h ON h.id=i.hospital_id
           WHERE i.medicine_id=?""",
        (disruption["medicine_id"],),
    ).fetchall()
    donor_by_id = {row["hospital_id"]: dict(row) for row in donor_rows}
    reservations = {row["hospital_id"]: 0 for row in donor_rows}
    recommendations = []
    checks = []

    for recipient in affected:
        remaining = int(recipient["uncovered_quantity"])
        if remaining <= 0:
            continue
        candidate_donors = []
        affected_ids = {row["hospital_id"] for row in affected}
        for donor in donor_rows:
            donor_id = donor["hospital_id"]
            if donor_id == recipient["hospital_id"] or donor_id in affected_ids:
                continue
            safe_surplus = transferable_surplus(donor["current_stock"], donor["safety_stock"], reservations[donor_id])
            if safe_surplus > 0:
                candidate_donors.append((city_distance(donor["city"], recipient["city"]), donor_id, safe_surplus))
        candidate_donors.sort()
        for distance, donor_id, surplus in candidate_donors:
            quantity = min(remaining, surplus)
            if quantity <= 0:
                continue
            donor = donor_by_id[donor_id]
            expected_stock_after = float(donor["current_stock"]) - reservations[donor_id] - quantity
            reason = (
                f"{recipient['hospital_name']} has {recipient['current_stock']:.0f} {recipient['unit']} and uses "
                f"{recipient['daily_demand']:.0f} per day. A {plan['arrival_days']:.0f}-day wait needs "
                f"{recipient['daily_demand'] * plan['arrival_days']:.0f}; the uncovered amount is "
                f"{recipient['uncovered_quantity']:.0f}. {donor['hospital_name']} can release {quantity} while "
                f"keeping {expected_stock_after:.0f} in stock against its {float(donor['safety_stock']):.0f} minimum."
            )
            benefit = (
                f"Bridges {quantity / max(recipient['daily_demand'], 0.001):.1f} days of demand "
                f"and is expected to reach {recipient['hospital_name']} before its projected shortage."
            )
            risk = (
                "Donor remains at or above its configured minimum safety stock. Route and stock figures are simulated."
                if expected_stock_after >= float(donor["safety_stock"])
                else "Transfer would breach minimum safety stock and must not be approved."
            )
            details = {
                "current_donor_stock": float(donor["current_stock"]),
                "donor_safety_stock": float(donor["safety_stock"]),
                "donor_stock_after": expected_stock_after,
                "donor_safety_check": transfer_preserves_safety(donor["current_stock"], donor["safety_stock"], reservations[donor_id] + quantity),
                "recipient_stock": recipient["current_stock"],
                "recipient_daily_demand": recipient["daily_demand"],
                "arrival_days": plan["arrival_days"],
                "coverage_gap": recipient["uncovered_quantity"],
                "distance_km": distance,
                "compatibility": True,
                "simulated": True,
            }
            recommendation_id = new_id("REC")
            connection.execute(
                """INSERT INTO recommendations
                   (id,disruption_id,recommendation_type,hospital_id,donor_hospital_id,supplier_id,
                    medicine_id,quantity,reason,benefit,risk,status,details_json,created_at)
                   VALUES (?,?,?,?,?,NULL,?,?,?,?,?, 'Pending approval',?,?)""",
                (recommendation_id, disruption["id"], "transfer", recipient["hospital_id"],
                 donor_id, disruption["medicine_id"], quantity, reason, benefit, risk,
                 json.dumps(details), now_iso()),
            )
            recommendations.append({
                "id": recommendation_id, "recommendation_type": "transfer",
                "hospital_id": recipient["hospital_id"], "hospital_name": recipient["hospital_name"],
                "donor_hospital_id": donor_id, "donor_hospital_name": donor["hospital_name"],
                "medicine_id": disruption["medicine_id"], "medicine_name": recipient["medicine_name"],
                "unit": recipient["unit"], "quantity": quantity, "reason": reason, "benefit": benefit,
                "risk": risk, "status": "Pending approval", "details": details,
            })
            reservations[donor_id] += quantity
            remaining -= quantity
            checks.append({
                "donor": donor["hospital_name"], "recipient": recipient["hospital_name"],
                "available_above_safety": surplus, "quantity": quantity,
                "safety_stock_preserved": expected_stock_after >= float(donor["safety_stock"]),
            })
            if remaining <= 0:
                break

    medicine = connection.execute("SELECT * FROM medicines WHERE id=?", (disruption["medicine_id"],)).fetchone()
    suppliers = connection.execute(
        """SELECT s.id AS supplier_id,s.name AS supplier_name,s.city,s.reliability,s.status,
                  sm.unit_price,sm.available_qty,sm.lead_days
           FROM supplier_medicines sm JOIN suppliers s ON s.id=sm.supplier_id
           WHERE sm.medicine_id=? AND sm.supplier_id<>? AND sm.available_qty>0 AND s.status='Available'
           ORDER BY sm.lead_days, s.reliability DESC""",
        (disruption["medicine_id"], medicine["primary_supplier_id"]),
    ).fetchall()
    target_gap = next(
        (x["uncovered_quantity"] for x in plan["hospitals"] if x["hospital_id"] == "ASTR"), 0
    )
    supplier_options = []
    for supplier in suppliers:
        supplier_options.append({
            "supplier_id": supplier["supplier_id"],
            "supplier_name": supplier["supplier_name"],
            "city": supplier["city"],
            "reliability": float(supplier["reliability"]),
            "available_qty": float(supplier["available_qty"]),
            "unit_price": float(supplier["unit_price"]),
            "lead_days": float(supplier["lead_days"]),
            "can_cover_target_gap": float(supplier["available_qty"]) >= int(target_gap),
            "reason": (
                f"{supplier['supplier_name']} lists {float(supplier['available_qty']):.0f} units at "
                f"USD {float(supplier['unit_price']):.2f} each with a simulated {float(supplier['lead_days']):g}-day lead time."
            ),
            "simulated": True,
        })
    result = {
        "recommendations": recommendations,
        "supplier_options": supplier_options,
        "allocation_checks": checks,
        "checks": {
            "safety_stock_enforced": all(item["safety_stock_preserved"] for item in checks),
            "no_negative_transfer": all(item["quantity"] > 0 for item in checks),
            "compatible_medicine": True,
            "all_affected_hospitals_considered": len(affected),
        },
        "generated_at": now_iso(),
    }
    record_audit(
        connection, "agent.inventory", "Inventory and Allocation Agent",
        f"Created {len(recommendations)} transfer proposal(s) after checking safety stock and {len(supplier_options)} alternative supplier(s).",
        "disruption", disruption["id"], {
            "recommendations": recommendations, "supplier_options": supplier_options,
            "allocation_checks": checks, "checks": result["checks"],
        },
    )
    return result
