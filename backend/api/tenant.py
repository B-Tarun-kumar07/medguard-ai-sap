"""Local authentication and pharmacy-isolated operational APIs for MedGuard AI 2.0.

The local demo uses self-contained PBKDF2 accounts. It deliberately has no external
identity provider or live provider integrations; production deployment can replace
the session dependency with Supabase/OIDC validation without changing the routes.
"""
from __future__ import annotations

import base64
import csv
import io
import json
import secrets
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, field_validator

from backend import db
from backend.agents.planning import days_of_stock

router = APIRouter(prefix="/api")
WRITE_ROLES = {"Platform Administrator", "Pharmacy Owner", "Pharmacist / Inventory Manager", "Pharmacy Staff"}


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=160)
    password: str = Field(min_length=8, max_length=160)


class RegisterRequest(LoginRequest):
    display_name: str = Field(min_length=2, max_length=80)
    hospital_id: str


class MovementRequest(BaseModel):
    medicine_id: str
    quantity: float = Field(gt=0, le=100000)
    movement_type: Literal["sale", "receipt", "return", "adjustment", "damaged", "expired"]
    batch_id: str | None = None
    note: str = Field(default="", max_length=300)


class BatchRequest(BaseModel):
    medicine_id: str
    batch_number: str = Field(min_length=2, max_length=80)
    manufacture_date: str | None = None
    expiry_date: str | None = None
    quantity: float = Field(gt=0, le=100000)
    source_label: str = Field(default="Manually verified by pharmacy", max_length=160)
    is_sample: bool = False


class ImportRequest(BaseModel):
    file_name: str = Field(min_length=3, max_length=180)
    content_base64: str = Field(min_length=2, max_length=2_000_000)
    confirmed: bool = False


class PurchaseOrderRequest(BaseModel):
    medicine_id: str
    supplier_id: str
    quantity: int = Field(ge=1, le=100000)


def _expires() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(timespec="seconds").replace("+00:00", "Z")


def _user_payload(row, connection):
    memberships = connection.execute(
        """SELECT pm.hospital_id,pm.role,h.name AS pharmacy_name FROM pharmacy_memberships pm
           JOIN hospitals h ON h.id=pm.hospital_id WHERE pm.user_id=? ORDER BY h.name""", (row["id"],)
    ).fetchall()
    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"],
            "role": row["role"], "memberships": [dict(item) for item in memberships], "demo_local_auth": True}


def require_session(x_session_token: str | None = Header(default=None)):
    if not x_session_token:
        raise HTTPException(401, "Sign in is required for pharmacy data.")
    with db.connect() as connection:
        row = connection.execute(
            """SELECT u.* FROM user_sessions s JOIN users u ON u.id=s.user_id
               WHERE s.token_hash=? AND s.expires_at>? AND u.active=1""",
            (db.session_hash(x_session_token), db.now_iso()),
        ).fetchone()
        if not row:
            raise HTTPException(401, "Your local demo session has expired. Sign in again.")
        return _user_payload(row, connection)


def _assert_access(user: dict, hospital_id: str, write: bool = False):
    membership = next((item for item in user["memberships"] if item["hospital_id"] == hospital_id), None)
    if user["role"] == "Platform Administrator":
        # Platform administration does not provide automatic customer-data access.
        if not membership:
            raise HTTPException(403, "Platform administrators need an explicit pharmacy membership to view pharmacy records.")
    if not membership:
        raise HTTPException(403, "You do not have access to this pharmacy's data.")
    if write and membership["role"] not in WRITE_ROLES:
        raise HTTPException(403, "Your pharmacy role is read-only.")
    return membership


@router.post("/auth/login")
def login(payload: LoginRequest):
    with db.connect() as connection:
        user = connection.execute("SELECT * FROM users WHERE lower(email)=lower(?) AND active=1", (payload.email.strip(),)).fetchone()
        if not user or not db.verify_password(payload.password, user["password_hash"]):
            raise HTTPException(401, "Email or password is incorrect.")
        token = secrets.token_urlsafe(32)
        connection.execute("INSERT INTO user_sessions(token_hash,user_id,expires_at,created_at) VALUES (?,?,?,?)",
            (db.session_hash(token), user["id"], _expires(), db.now_iso()))
        db.record_audit(connection, "auth.login", user["display_name"], "Signed in to the local demo account.", "user", user["id"], {"simulated": True})
        return {"token": token, "user": _user_payload(user, connection), "expires_at": _expires()}


@router.post("/auth/register")
def register(payload: RegisterRequest):
    with db.connect() as connection:
        if connection.execute("SELECT 1 FROM users WHERE lower(email)=lower(?)", (payload.email.strip(),)).fetchone():
            raise HTTPException(409, "An account with this email already exists.")
        if not connection.execute("SELECT 1 FROM hospitals WHERE id=?", (payload.hospital_id,)).fetchone():
            raise HTTPException(404, "Choose a valid pharmacy.")
        user_id = db.new_id("USR")
        connection.execute("INSERT INTO users(id,email,display_name,password_hash,role,active,created_at) VALUES (?,?,?,?,?,?,?)",
            (user_id, payload.email.strip().lower(), payload.display_name.strip(), db.password_hash(payload.password), "Pharmacy Staff", 1, db.now_iso()))
        connection.execute("INSERT INTO pharmacy_memberships(user_id,hospital_id,role) VALUES (?,?,?)", (user_id, payload.hospital_id, "Pharmacy Staff"))
        db.record_audit(connection, "auth.register", payload.display_name.strip(), "Registered a local demo pharmacy staff account.", "user", user_id, {"hospital_id": payload.hospital_id, "simulated": True})
        return {"message": "Local demo account created. Sign in to continue.", "user_id": user_id}


@router.get("/auth/me")
def me(user: dict = Depends(require_session)):
    return user


@router.post("/auth/logout")
def logout(x_session_token: str | None = Header(default=None), user: dict = Depends(require_session)):
    with db.connect() as connection:
        connection.execute("DELETE FROM user_sessions WHERE token_hash=?", (db.session_hash(x_session_token or ""),))
        db.record_audit(connection, "auth.logout", user["display_name"], "Signed out of the local demo account.", "user", user["id"], {"simulated": True})
    return {"status": "signed_out"}


@router.get("/tenant/{hospital_id}/inventory")
def tenant_inventory(hospital_id: str, user: dict = Depends(require_session)):
    _assert_access(user, hospital_id)
    with db.connect() as connection:
        rows = connection.execute(
            """SELECT i.*,m.name medicine_name,m.unit,m.criticality,m.manufacture_date,m.expiry_date,h.name pharmacy_name
               FROM inventory i JOIN medicines m ON m.id=i.medicine_id JOIN hospitals h ON h.id=i.hospital_id
               WHERE i.hospital_id=? ORDER BY m.name""", (hospital_id,)).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["days_remaining"] = days_of_stock(item["current_stock"], item["daily_demand"])
            item["reorder_point"] = round(float(item["daily_demand"] or 0) * 2 + float(item["safety_stock"]), 1)
            output.append(item)
        return output


@router.get("/tenant/{hospital_id}/batches")
def batches(hospital_id: str, user: dict = Depends(require_session)):
    _assert_access(user, hospital_id)
    with db.connect() as connection:
        rows = connection.execute(
            """SELECT b.*,m.name medicine_name,m.unit FROM medicine_batches b JOIN medicines m ON m.id=b.medicine_id
               WHERE b.hospital_id=? ORDER BY b.expiry_date,b.medicine_id""", (hospital_id,)).fetchall()
    return [dict(row) for row in rows]


@router.post("/tenant/{hospital_id}/batches")
def add_batch(hospital_id: str, payload: BatchRequest, user: dict = Depends(require_session)):
    _assert_access(user, hospital_id, write=True)
    with db.connect() as connection:
        if not connection.execute("SELECT 1 FROM medicines WHERE id=?", (payload.medicine_id,)).fetchone():
            raise HTTPException(404, "Medicine was not found.")
        if payload.expiry_date and payload.manufacture_date and payload.expiry_date <= payload.manufacture_date:
            raise HTTPException(422, "Expiry date must be after manufacture date.")
        batch_id = db.new_id("BAT")
        try:
            connection.execute("INSERT INTO medicine_batches(id,hospital_id,medicine_id,batch_number,manufacture_date,expiry_date,quantity_available,source_label,is_sample,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (batch_id, hospital_id, payload.medicine_id, payload.batch_number.strip(), payload.manufacture_date, payload.expiry_date,
                 payload.quantity, payload.source_label.strip(), int(payload.is_sample), db.now_iso()))
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                raise HTTPException(409, "A batch with that number already exists for this medicine at this pharmacy.") from exc
            raise
        connection.execute("UPDATE inventory SET current_stock=current_stock+?,updated_at=? WHERE hospital_id=? AND medicine_id=?",
            (payload.quantity, db.now_iso(), hospital_id, payload.medicine_id))
        movement_id = db.new_id("MOV")
        connection.execute("INSERT INTO stock_movements(id,hospital_id,medicine_id,batch_id,movement_type,quantity,note,actor,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (movement_id, hospital_id, payload.medicine_id, batch_id, "receipt", payload.quantity, "Batch received", user["display_name"], db.now_iso()))
        db.record_audit(connection, "batch.received", user["display_name"], f"Recorded batch {payload.batch_number} with {payload.quantity:g} units.", "batch", batch_id, {"hospital_id": hospital_id, "sample": payload.is_sample})
    return {"batch_id": batch_id, "movement_id": movement_id, "message": "Batch and inventory receipt recorded."}


@router.post("/tenant/{hospital_id}/movements")
def stock_movement(hospital_id: str, payload: MovementRequest, user: dict = Depends(require_session)):
    _assert_access(user, hospital_id, write=True)
    incoming = payload.movement_type in {"receipt", "return"}
    with db.connect() as connection:
        inventory = connection.execute("SELECT current_stock FROM inventory WHERE hospital_id=? AND medicine_id=?", (hospital_id, payload.medicine_id)).fetchone()
        if not inventory:
            raise HTTPException(404, "Inventory record was not found.")
        sign = 1 if incoming else -1
        current = float(inventory["current_stock"])
        if sign < 0 and current < payload.quantity:
            raise HTTPException(409, "This movement would make inventory negative.")
        batch = None
        if payload.batch_id:
            batch = connection.execute("SELECT * FROM medicine_batches WHERE id=? AND hospital_id=? AND medicine_id=?", (payload.batch_id, hospital_id, payload.medicine_id)).fetchone()
            if not batch:
                raise HTTPException(404, "The selected batch is unavailable for this pharmacy and medicine.")
            if sign < 0 and float(batch["quantity_available"]) < payload.quantity:
                raise HTTPException(409, "This movement exceeds the selected batch quantity.")
            connection.execute("UPDATE medicine_batches SET quantity_available=quantity_available+?,updated_at=? WHERE id=?", (sign * payload.quantity, db.now_iso(), payload.batch_id))
        connection.execute("UPDATE inventory SET current_stock=current_stock+?,updated_at=? WHERE hospital_id=? AND medicine_id=?", (sign * payload.quantity, db.now_iso(), hospital_id, payload.medicine_id))
        movement_id = db.new_id("MOV")
        connection.execute("INSERT INTO stock_movements(id,hospital_id,medicine_id,batch_id,movement_type,quantity,note,actor,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (movement_id, hospital_id, payload.medicine_id, payload.batch_id, payload.movement_type, payload.quantity, payload.note, user["display_name"], db.now_iso()))
        if payload.movement_type == "sale":
            connection.execute("INSERT INTO sales_transactions(id,hospital_id,medicine_id,quantity,sold_at) VALUES (?,?,?,?,?)", (db.new_id("SALE"), hospital_id, payload.medicine_id, payload.quantity, db.now_iso()))
        db.record_audit(connection, f"stock.{payload.movement_type}", user["display_name"], f"Recorded {payload.movement_type} of {payload.quantity:g} units.", "stock_movement", movement_id, {"hospital_id": hospital_id, "medicine_id": payload.medicine_id})
        return {"movement_id": movement_id, "remaining_stock": current + sign * payload.quantity}


@router.get("/tenant/{hospital_id}/movements")
def movements(hospital_id: str, user: dict = Depends(require_session)):
    _assert_access(user, hospital_id)
    with db.connect() as connection:
        rows = connection.execute("""SELECT sm.*,m.name medicine_name,m.unit,b.batch_number FROM stock_movements sm
          JOIN medicines m ON m.id=sm.medicine_id LEFT JOIN medicine_batches b ON b.id=sm.batch_id
          WHERE sm.hospital_id=? ORDER BY sm.created_at DESC LIMIT 200""", (hospital_id,)).fetchall()
    return [dict(row) for row in rows]


@router.get("/tenant/{hospital_id}/forecast")
def forecast(hospital_id: str, user: dict = Depends(require_session)):
    _assert_access(user, hospital_id)
    with db.connect() as connection:
        rows = connection.execute("""SELECT i.*,m.name medicine_name,m.unit FROM inventory i JOIN medicines m ON m.id=i.medicine_id
          WHERE i.hospital_id=? ORDER BY m.name""", (hospital_id,)).fetchall()
        forecasts = []
        for item in rows:
            sales = connection.execute("SELECT COALESCE(SUM(quantity),0) total,COUNT(*) count FROM sales_transactions WHERE hospital_id=? AND medicine_id=? AND sold_at>=?",
                (hospital_id, item["medicine_id"], (datetime.now(timezone.utc)-timedelta(days=30)).isoformat())).fetchone()
            observed_daily = float(sales["total"]) / 30 if sales["count"] else None
            baseline = float(item["daily_demand"] or 0)
            demand = round(observed_daily if observed_daily and observed_daily > 0 else baseline, 2)
            method = "30-day recorded sales average" if observed_daily and observed_daily > 0 else "configured demo daily-demand baseline"
            confidence = "Low — limited recorded sales" if not sales["count"] or sales["count"] < 7 else "Moderate — based on recorded sales"
            reorder = round(demand * 2 + float(item["safety_stock"]), 1)
            forecasts.append({"medicine_id": item["medicine_id"], "medicine_name": item["medicine_name"], "unit": item["unit"],
                "current_stock": item["current_stock"], "expected_daily_demand": demand, "days_remaining": days_of_stock(item["current_stock"], demand),
                "reorder_point": reorder, "suggested_reorder_quantity": max(0, round(reorder * 2 - float(item["current_stock"]))), "method": method, "confidence": confidence})
    return {"pharmacy_id": hospital_id, "forecast_window_days": 14, "forecasts": forecasts, "simulated": True}


@router.get("/tenant/{hospital_id}/notifications")
def notifications(hospital_id: str, user: dict = Depends(require_session)):
    _assert_access(user, hospital_id)
    with db.connect() as connection:
        rows = connection.execute("SELECT * FROM notifications WHERE hospital_id=? ORDER BY CASE status WHEN 'unread' THEN 0 ELSE 1 END,created_at DESC", (hospital_id,)).fetchall()
    return [dict(row) for row in rows]


@router.post("/tenant/{hospital_id}/notifications/{notification_id}/read")
def mark_notification_read(hospital_id: str, notification_id: str, user: dict = Depends(require_session)):
    _assert_access(user, hospital_id)
    with db.connect() as connection:
        changed = connection.execute("UPDATE notifications SET status='read',read_at=? WHERE id=? AND hospital_id=?", (db.now_iso(), notification_id, hospital_id)).rowcount
        if not changed:
            raise HTTPException(404, "Notification was not found.")
    return {"status": "read"}


def _rows_from_upload(payload: ImportRequest) -> list[dict[str, str]]:
    try:
        content = base64.b64decode(payload.content_base64, validate=True)
    except Exception as exc:
        raise HTTPException(422, "The uploaded file could not be decoded.") from exc
    name = payload.file_name.lower()
    if name.endswith(".csv"):
        try:
            return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        except UnicodeDecodeError as exc:
            raise HTTPException(422, "CSV must use UTF-8 encoding.") from exc
    if name.endswith(".xlsx"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                shared = []
                if "xl/sharedStrings.xml" in archive.namelist():
                    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                    shared = ["".join(node.itertext()) for node in root]
                root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
                ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                grid = []
                for row in root.findall(".//m:row", ns):
                    values = []
                    for cell in row.findall("m:c", ns):
                        value = cell.findtext("m:v", default="", namespaces=ns)
                        if cell.get("t") == "s" and value:
                            value = shared[int(value)]
                        inline = cell.find("m:is", ns)
                        if inline is not None:
                            value = "".join(inline.itertext())
                        values.append(value)
                    grid.append(values)
                if not grid:
                    return []
                headers = [str(value).strip() for value in grid[0]]
                return [dict(zip(headers, [str(value) for value in row])) for row in grid[1:] if any(row)]
        except (KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
            raise HTTPException(422, "This XLSX file could not be read. Use the template or a standard first-sheet workbook.") from exc
    raise HTTPException(422, "Upload a CSV or XLSX file.")


@router.post("/tenant/{hospital_id}/import/preview")
def import_preview(hospital_id: str, payload: ImportRequest, user: dict = Depends(require_session)):
    _assert_access(user, hospital_id, write=True)
    rows = _rows_from_upload(payload)
    required = {"medicine_id", "batch_number", "quantity"}
    if not rows:
        raise HTTPException(422, "No data rows were found.")
    missing = required - set(rows[0])
    if missing:
        raise HTTPException(422, "Missing required columns: " + ", ".join(sorted(missing)))
    with db.connect() as connection:
        valid, errors = [], []
        seen = set()
        for index, row in enumerate(rows, 2):
            medicine_id = (row.get("medicine_id") or "").strip().upper()
            batch_number = (row.get("batch_number") or "").strip()
            try:
                quantity = float(row.get("quantity") or 0)
            except ValueError:
                quantity = 0
            duplicate = (medicine_id, batch_number) in seen or connection.execute("SELECT 1 FROM medicine_batches WHERE hospital_id=? AND medicine_id=? AND batch_number=?", (hospital_id, medicine_id, batch_number)).fetchone()
            if not connection.execute("SELECT 1 FROM medicines WHERE id=?", (medicine_id,)).fetchone():
                errors.append({"row": index, "message": f"Unknown medicine_id: {medicine_id or '(blank)'}"})
            elif not batch_number or quantity <= 0:
                errors.append({"row": index, "message": "batch_number and positive quantity are required."})
            elif duplicate:
                errors.append({"row": index, "message": "Duplicate batch in the upload or existing inventory."})
            else:
                valid.append({"medicine_id": medicine_id, "batch_number": batch_number, "quantity": quantity,
                              "manufacture_date": row.get("manufacture_date") or None, "expiry_date": row.get("expiry_date") or None,
                              "source_label": row.get("source_label") or "Imported by pharmacy", "is_sample": str(row.get("is_sample", "false")).lower() in {"true", "yes", "1"}})
                seen.add((medicine_id, batch_number))
    return {"file_name": payload.file_name, "valid_rows": valid, "errors": errors, "ready_to_import": bool(valid) and not errors}


@router.post("/tenant/{hospital_id}/import/commit")
def import_commit(hospital_id: str, payload: ImportRequest, user: dict = Depends(require_session)):
    _assert_access(user, hospital_id, write=True)
    if not payload.confirmed:
        raise HTTPException(422, "Confirm the preview before importing.")
    preview = import_preview(hospital_id, payload.model_copy(update={"confirmed": False}), user)
    if preview["errors"]:
        raise HTTPException(422, {"message": "Fix the preview errors before importing.", "errors": preview["errors"]})
    with db.connect() as connection:
        for item in preview["valid_rows"]:
            batch_id = db.new_id("BAT")
            connection.execute("INSERT INTO medicine_batches(id,hospital_id,medicine_id,batch_number,manufacture_date,expiry_date,quantity_available,source_label,is_sample,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (batch_id, hospital_id, item["medicine_id"], item["batch_number"], item["manufacture_date"], item["expiry_date"], item["quantity"], item["source_label"], int(item["is_sample"]), db.now_iso()))
            connection.execute("UPDATE inventory SET current_stock=current_stock+?,updated_at=? WHERE hospital_id=? AND medicine_id=?", (item["quantity"], db.now_iso(), hospital_id, item["medicine_id"]))
            connection.execute("INSERT INTO stock_movements(id,hospital_id,medicine_id,batch_id,movement_type,quantity,note,actor,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (db.new_id("MOV"), hospital_id, item["medicine_id"], batch_id, "receipt", item["quantity"], f"Import: {payload.file_name}", user["display_name"], db.now_iso()))
        db.record_audit(connection, "inventory.import", user["display_name"], f"Imported {len(preview['valid_rows'])} validated batch rows from {payload.file_name}.", "pharmacy", hospital_id, {"file_name": payload.file_name, "rows": len(preview["valid_rows"]), "simulated": True})
    return {"imported": len(preview["valid_rows"]), "message": "Validated inventory import completed."}


@router.get("/tenant/import-template.csv")
def import_template():
    return PlainTextResponse("medicine_id,batch_number,manufacture_date,expiry_date,quantity,source_label,is_sample\nNOREPI,DEMO-ASTER-NOR-02,2026-01-01,2027-07-01,20,Example sample batch,true\n", media_type="text/csv", headers={"Content-Disposition": "attachment; filename=medguard_inventory_template.csv"})

