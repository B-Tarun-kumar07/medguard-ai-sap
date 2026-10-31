from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from backend import db
from backend.api.common import days_until
from backend.integrations.sap import publish_shipment_status

router = APIRouter(prefix="/api")


class LocationUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    speed_mps: float | None = Field(default=None, ge=0)
    heading_deg: float | None = Field(default=None, ge=0, le=360)


@router.get("/shipments/{shipment_id}/tracking")
def get_shipment_tracking(shipment_id: str):
    with db.connect() as connection:
        shipment = connection.execute(
            "SELECT id,status,tracking_json,source_label,destination_id FROM shipments WHERE id=?",
            (shipment_id,),
        ).fetchone()

        if not shipment:
            raise HTTPException(404, "Shipment not found.")

        import json

        tracking = json.loads(shipment["tracking_json"] or "{}")

        return {
            "shipment_id": shipment["id"],
            "status": shipment["status"],
            "tracking": tracking,
            "source": shipment["source_label"],
        }


@router.post("/shipments/{shipment_id}/location")
def update_shipment_location(shipment_id: str, location: LocationUpdate):
    import json

    with db.connect() as connection:
        shipment = connection.execute(
            "SELECT status,tracking_json FROM shipments WHERE id=?", (shipment_id,)
        ).fetchone()
        if not shipment:
            raise HTTPException(404, "Shipment not found.")
        if shipment["status"] not in ("Dispatched", "In Transit", "Delayed"):
            raise HTTPException(409, "Location can only be shared for an active shipment.")

        tracking = json.loads(shipment["tracking_json"] or "{}")
        tracking["location"] = {
            **location.model_dump(exclude_none=True),
            "recorded_at": db.now_iso(),
        }
        tracking["simulated"] = False
        connection.execute(
            "UPDATE shipments SET tracking_json=? WHERE id=?",
            (json.dumps(tracking), shipment_id),
        )
        return {"shipment_id": shipment_id, "location": tracking["location"]}


@router.post("/shipments/{shipment_id}/location/stop")
def stop_shipment_location(shipment_id: str):
    import json

    with db.connect() as connection:
        shipment = connection.execute(
            "SELECT tracking_json FROM shipments WHERE id=?", (shipment_id,)
        ).fetchone()
        if not shipment:
            raise HTTPException(404, "Shipment not found.")
        tracking = json.loads(shipment["tracking_json"] or "{}")
        tracking.pop("location", None)
        connection.execute(
            "UPDATE shipments SET tracking_json=? WHERE id=?",
            (json.dumps(tracking), shipment_id),
        )
        return {"shipment_id": shipment_id, "sharing": False}


@router.post("/shipments/{shipment_id}/tracking")
def update_shipment_tracking(
    shipment_id: str,
    stage: Literal[
        "driver_assigned",
        "going_to_pickup",
        "picked_up",
        "on_the_way",
        "delivered",
    ] = Query(...),
):
    import json
    import random

    with db.connect() as connection:
        shipment = connection.execute(
            "SELECT * FROM shipments WHERE id=?",
            (shipment_id,),
        ).fetchone()

        if not shipment:
            raise HTTPException(404, "Shipment not found.")

        tracking = json.loads(shipment["tracking_json"] or "{}")

        stages = {
            "driver_assigned": "Driver assigned",
            "going_to_pickup": "Going to pickup",
            "picked_up": "Medicine picked up",
            "on_the_way": "On the way to hospital",
            "delivered": "Delivered",
        }

        tracking.update({
            "stage": stage,
            "stage_label": stages[stage],
            "updated_at": db.now_iso(),
            "simulated": True,
        })

        if stage == "driver_assigned":
            tracking.update({
                "driver_name": "Arjun Kumar",
                "vehicle": "Medical delivery van",
                "vehicle_number": "KA 03 MG 2026",
            })

        if stage == "on_the_way":
            tracking.update({
                "traffic": random.choice(["Light", "Moderate", "Heavy"]),
                "eta_minutes": random.choice([12, 18, 24, 30, 36]),
                "progress": 0.05,
            })

        if stage == "delivered":
            tracking["progress"] = 1.0

        connection.execute(
            "UPDATE shipments SET tracking_json=? WHERE id=?",
            (json.dumps(tracking), shipment_id),
        )

        db.record_audit(
            connection,
            "shipment.updated",
            "Logistics operator",
            f"Shipment tracking updated: {stages[stage]}.",
            "shipment",
            shipment_id,
            {"stage": stage, "simulated": True},
        )

        return {
            "shipment_id": shipment_id,
            "tracking": tracking,
            "message": "Tracking updated successfully.",
        }
@router.post("/shipments/{shipment_id}/advance")
def advance_shipment(
    shipment_id: str,
    background_tasks: BackgroundTasks,
    status: Literal["Dispatched", "In Transit", "Delayed", "Delivered"] = Query(...),
):
    with db.connect() as connection:
        shipment = connection.execute("SELECT * FROM shipments WHERE id=?", (shipment_id,)).fetchone()
        if not shipment:
            raise HTTPException(404, "Shipment not found.")
        allowed = {
            "Approved": {"Dispatched"},
            "Dispatched": {"In Transit"},
            "In Transit": {"Delayed", "Delivered"},
            "Delayed": {"In Transit", "Delivered"},
            "Delivered": set(),
        }
        if status not in allowed.get(shipment["status"], set()):
            raise HTTPException(409, f"Cannot move shipment from {shipment['status']} to {status}.")
        if status == "Dispatched":
            quantity = float(shipment["quantity"])
            if shipment["source_type"] == "hospital":
                donor = connection.execute(
                    "SELECT current_stock,safety_stock FROM inventory WHERE hospital_id=? AND medicine_id=?",
                    (shipment["source_id"], shipment["medicine_id"]),
                ).fetchone()
                if not donor or float(donor["current_stock"]) - quantity < float(donor["safety_stock"]):
                    raise HTTPException(409, "Dispatch would breach the donor's minimum safety stock.")
                connection.execute(
                    """UPDATE inventory SET current_stock=current_stock-?,updated_at=?
                       WHERE hospital_id=? AND medicine_id=?""",
                    (quantity, db.now_iso(), shipment["source_id"], shipment["medicine_id"]),
                )
            elif shipment["source_type"] == "supplier":
                supply = connection.execute(
                    "SELECT available_qty FROM supplier_medicines WHERE supplier_id=? AND medicine_id=?",
                    (shipment["source_id"], shipment["medicine_id"]),
                ).fetchone()
                if not supply or float(supply["available_qty"]) < quantity:
                    raise HTTPException(409, "Supplier availability no longer covers this order.")
                connection.execute(
                    "UPDATE supplier_medicines SET available_qty=available_qty-? WHERE supplier_id=? AND medicine_id=?",
                    (quantity, shipment["source_id"], shipment["medicine_id"]),
                )
        if status == "Delayed":
            new_eta = float(shipment["eta_hours"]) + 12
            connection.execute(
                "UPDATE shipments SET status=?,eta_hours=?,expected_arrival=? WHERE id=?",
                (status, new_eta, days_until(new_eta), shipment_id),
            )
        elif status == "Delivered":
            connection.execute(
                """UPDATE inventory SET current_stock=current_stock+?,updated_at=?
                   WHERE hospital_id=? AND medicine_id=?""",
                (shipment["quantity"], db.now_iso(), shipment["destination_id"], shipment["medicine_id"]),
            )
            connection.execute(
                "UPDATE shipments SET status=?,delivered_at=?,eta_hours=0,expected_arrival=? WHERE id=?",
                (status, db.now_iso(), db.now_iso(), shipment_id),
            )
            if shipment["recommendation_id"]:
                connection.execute("UPDATE recommendations SET status='Delivered' WHERE id=?", (shipment["recommendation_id"],))
                rec = connection.execute(
                    "SELECT disruption_id FROM recommendations WHERE id=?",
                    (shipment["recommendation_id"],),
                ).fetchone()
                unfinished = connection.execute(
                    "SELECT COUNT(*) FROM recommendations WHERE disruption_id=? AND status<>'Delivered'",
                    (rec["disruption_id"],),
                ).fetchone()[0]
                if unfinished == 0:
                    connection.execute("UPDATE disruptions SET status='recovered' WHERE id=?", (rec["disruption_id"],))
        else:
            connection.execute("UPDATE shipments SET status=? WHERE id=?", (status, shipment_id))
        db.record_audit(
            connection, "shipment.updated", "Logistics operator",
            f"Shipment {shipment_id} advanced from {shipment['status']} to {status}.",
            "shipment", shipment_id, {
                "from_status": shipment["status"], "to_status": status,
                "quantity": float(shipment["quantity"]), "simulated": True,
            },
        )
        current_shipment = connection.execute(
            "SELECT expected_arrival FROM shipments WHERE id=?", (shipment_id,)
        ).fetchone()
        background_tasks.add_task(publish_shipment_status, {
            "shipment_id": shipment_id,
            "status": status,
            "source": shipment["source_label"],
            "destination_id": shipment["destination_id"],
            "medicine_id": shipment["medicine_id"],
            "quantity": float(shipment["quantity"]),
            "expected_arrival": current_shipment["expected_arrival"],
        })
        return {"shipment_id": shipment_id, "status": status, "message": "Shipment and audit log updated."}
