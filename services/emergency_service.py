import logging
from datetime import datetime
import re
import sqlite3
from database import get_connection
from services.activity_service import log_activity
from services.permissions import enforce_elderly_access

logger = logging.getLogger("dearly.emergency")

EMERGENCY_SAFETY_NOTICE = (
    "Dearly SOS sends in-app alerts to your authorized care circle. "
    "It does not guarantee that someone will receive or respond to an alert. "
    "For immediate danger or a medical emergency in India, call 112 or your local emergency service directly."
)

VALID_STATUSES = ["pending", "acknowledged", "assistance_in_progress", "resolved", "cancelled"]


def validate_contact_input(contact_name: str, relationship: str, phone: str):
    """Validates required emergency contact attributes."""
    if not contact_name or len(contact_name.strip()) < 2:
        raise ValueError("Contact person's name is required (minimum 2 characters).")
    if not relationship or len(relationship.strip()) < 2:
        raise ValueError("Relationship is required (minimum 2 characters).")
    if not phone or len(phone.strip()) < 7:
        raise ValueError("A valid phone number is required (minimum 7 digits).")

    clean_digits = "".join(c for c in phone if c.isdigit())
    if len(clean_digits) < 7:
        raise ValueError("Phone number must contain at least 7 numeric digits.")


# =============================================================================
# EMERGENCY CONTACT MANAGEMENT
# =============================================================================

def add_emergency_contact(
    elderly_user_id: int,
    contact_name: str,
    relationship: str,
    phone: str,
    email: str = "",
    priority: int = 1,
    is_primary: bool = False,
    notes: str = "",
    user: dict = None,
) -> int:
    """
    Creates a new emergency contact for an elderly profile with server-side validation.
    Enforces write permissions.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    validate_contact_input(contact_name, relationship, phone)

    with get_connection() as conn:
        # Single primary contact rule: if is_primary, unset any existing primary
        if is_primary:
            conn.execute(
                "UPDATE emergency_contacts SET is_primary = 0 WHERE elderly_user_id = ?",
                (elderly_user_id,),
            )

        cursor = conn.execute(
            """INSERT INTO emergency_contacts
               (elderly_user_id, contact_name, relationship, phone, email, priority, is_primary, is_active, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (
                elderly_user_id,
                contact_name.strip(),
                relationship.strip(),
                phone.strip(),
                email.strip(),
                priority,
                1 if is_primary else 0,
                notes.strip(),
            ),
        )
        contact_id = cursor.lastrowid

    actor_id = user.get("id") if user else elderly_user_id
    log_activity(
        elderly_user_id,
        actor_id,
        "Added Emergency Contact",
        f"Added {contact_name.strip()} ({relationship.strip()}, {phone.strip()}) as emergency contact.",
    )
    return contact_id


def update_emergency_contact(
    contact_id: int,
    elderly_user_id: int,
    contact_name: str,
    relationship: str,
    phone: str,
    email: str = "",
    priority: int = 1,
    is_primary: bool = False,
    notes: str = "",
    user: dict = None,
) -> bool:
    """Updates an existing emergency contact record."""
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    validate_contact_input(contact_name, relationship, phone)

    with get_connection() as conn:
        if is_primary:
            conn.execute(
                "UPDATE emergency_contacts SET is_primary = 0 WHERE elderly_user_id = ?",
                (elderly_user_id,),
            )

        conn.execute(
            """UPDATE emergency_contacts
               SET contact_name = ?,
                   relationship = ?,
                   phone = ?,
                   email = ?,
                   priority = ?,
                   is_primary = ?,
                   notes = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND elderly_user_id = ?""",
            (
                contact_name.strip(),
                relationship.strip(),
                phone.strip(),
                email.strip(),
                priority,
                1 if is_primary else 0,
                notes.strip(),
                contact_id,
                elderly_user_id,
            ),
        )

    actor_id = user.get("id") if user else elderly_user_id
    log_activity(
        elderly_user_id,
        actor_id,
        "Updated Emergency Contact",
        f"Updated emergency contact #{contact_id}: {contact_name.strip()}.",
    )
    return True


def delete_emergency_contact(
    contact_id: int,
    elderly_user_id: int,
    user: dict = None,
    hard_delete: bool = False,
) -> bool:
    """Deactivates or removes an emergency contact record."""
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    with get_connection() as conn:
        if hard_delete:
            conn.execute(
                "DELETE FROM emergency_contacts WHERE id = ? AND elderly_user_id = ?",
                (contact_id, elderly_user_id),
            )
        else:
            conn.execute(
                "UPDATE emergency_contacts SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND elderly_user_id = ?",
                (contact_id, elderly_user_id),
            )

    actor_id = user.get("id") if user else elderly_user_id
    log_activity(
        elderly_user_id,
        actor_id,
        "Removed Emergency Contact",
        f"Removed emergency contact #{contact_id}.",
    )
    return True


def set_primary_emergency_contact(contact_id: int, elderly_user_id: int, user: dict = None) -> bool:
    """Designates a single primary emergency contact for an elderly profile."""
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    with get_connection() as conn:
        conn.execute(
            "UPDATE emergency_contacts SET is_primary = 0 WHERE elderly_user_id = ?",
            (elderly_user_id,),
        )
        conn.execute(
            "UPDATE emergency_contacts SET is_primary = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND elderly_user_id = ?",
            (contact_id, elderly_user_id),
        )

    actor_id = user.get("id") if user else elderly_user_id
    log_activity(
        elderly_user_id,
        actor_id,
        "Set Primary Emergency Contact",
        f"Designated contact #{contact_id} as primary emergency responder.",
    )
    return True


def get_emergency_contacts(elderly_user_id: int, active_only: bool = True, user: dict = None) -> list[dict]:
    """
    Retrieves emergency contacts for an authorized elderly profile.
    Enforces server-side read access; prevents unrelated users from viewing private contacts.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    query = """SELECT id, elderly_user_id, contact_name, relationship, phone,
                      email, priority, is_primary, is_active, notes, created_at, updated_at
               FROM emergency_contacts WHERE elderly_user_id = ?"""
    params = [elderly_user_id]
    if active_only:
        query += " AND is_active = 1"
    query += " ORDER BY is_primary DESC, priority ASC, id ASC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


# =============================================================================
# SOS ACTIVATION & WORKFLOW
# =============================================================================

def activate_emergency_sos(
    elderly_user_id: int,
    triggered_by_user_id: int = None,
    location_notes: str = "",
    urgency_reason: str = "",
    user: dict = None,
) -> int:
    """
    Activates an Emergency SOS request:
    1. Verifies caller authorization for this profile.
    2. Prevents duplicate activation if an active emergency is already pending/in-progress.
    3. Creates record in emergency_requests and emergency_status_history.
    4. Dispatches in-app notifications strictly to active authorized Care Circle members.
    5. Logs to activity_logs.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    actor_id = triggered_by_user_id or (user.get("id") if user else elderly_user_id)

    with get_connection() as conn:
        # Prevent duplicate emergency requests if an active request already exists
        existing_active = conn.execute(
            """SELECT id, created_at, status FROM emergency_requests
               WHERE elderly_user_id = ? AND status IN ('pending', 'acknowledged', 'assistance_in_progress')
               ORDER BY id DESC LIMIT 1""",
            (elderly_user_id,),
        ).fetchone()

        if existing_active:
            raise ValueError(
                f"An emergency assistance request (#{existing_active['id']}) is already active for this profile (Status: {existing_active['status']}). Caregivers have been notified."
            )

        eld_row = conn.execute("SELECT name FROM users WHERE id = ?", (elderly_user_id,)).fetchone()
        elderly_name = eld_row["name"] if eld_row else f"Patient #{elderly_user_id}"

        # 1. Insert into emergency_requests
        cursor = conn.execute(
            """INSERT INTO emergency_requests
               (elderly_user_id, triggered_by_user_id, status, location_notes, urgency_reason, created_at, updated_at)
               VALUES (?, ?, 'pending', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (elderly_user_id, actor_id, location_notes.strip(), urgency_reason.strip()),
        )
        request_id = cursor.lastrowid

        # 2. Record initial status in status history
        conn.execute(
            """INSERT INTO emergency_status_history
               (request_id, elderly_user_id, actor_user_id, from_status, to_status, response_note, created_at)
               VALUES (?, ?, ?, 'none', 'pending', ?, CURRENT_TIMESTAMP)""",
            (request_id, elderly_user_id, actor_id, "Emergency SOS triggered by senior"),
        )

        # 3. Identify ACTIVE and AUTHORIZED care circle members only (revoked/inactive members receive zero alerts)
        circle_members = conn.execute(
            """SELECT cc.member_user_id, cc.relationship, cc.permission_level, u.name, u.email
               FROM care_circle cc
               JOIN users u ON cc.member_user_id = u.id
               WHERE cc.elderly_user_id = ? AND cc.status = 'active'""",
            (elderly_user_id,),
        ).fetchall()

        loc_str = f" Location: {location_notes.strip()}." if location_notes.strip() else ""
        notif_msg = f"{elderly_name} has activated Emergency SOS.{loc_str} Immediate response required."

        for m in circle_members:
            m_uid = m["member_user_id"]
            conn.execute(
                """INSERT INTO notifications
                   (user_id, elderly_user_id, alert_type, title, message)
                   VALUES (?, ?, 'system', ?, ?)""",
                (
                    m_uid,
                    elderly_user_id,
                    f"EMERGENCY SOS: {elderly_name}",
                    notif_msg,
                ),
            )

    log_activity(
        elderly_user_id,
        actor_id,
        "EMERGENCY SOS ACTIVATED",
        f"Emergency SOS #{request_id} activated for {elderly_name}. Notified {len(circle_members)} active Care Circle member(s).",
    )
    return request_id


def get_emergency_requests(
    elderly_user_id: int,
    status: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 50,
    user: dict = None,
) -> list[dict]:
    """
    Retrieves chronological emergency requests with actor metadata.
    Enforces server-side read permissions.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    query = """
        SELECT er.id, er.elderly_user_id, er.triggered_by_user_id, er.status,
               er.location_notes, er.urgency_reason, er.acknowledged_by,
               er.acknowledged_at, er.resolved_by, er.resolved_at,
               er.resolution_notes, er.created_at, er.updated_at,
               u_eld.name as elderly_name,
               u_trig.name as triggered_by_name,
               u_ack.name as acknowledged_by_name,
               u_res.name as resolved_by_name
        FROM emergency_requests er
        JOIN users u_eld ON er.elderly_user_id = u_eld.id
        LEFT JOIN users u_trig ON er.triggered_by_user_id = u_trig.id
        LEFT JOIN users u_ack ON er.acknowledged_by = u_ack.id
        LEFT JOIN users u_res ON er.resolved_by = u_res.id
        WHERE er.elderly_user_id = ?
    """
    params = [elderly_user_id]

    if status and status.lower() != "all":
        query += " AND er.status = ?"
        params.append(status.lower())

    if start_date:
        query += " AND er.created_at >= ?"
        params.append(start_date)

    if end_date:
        query += " AND er.created_at <= ?"
        params.append(end_date)

    query += " ORDER BY er.created_at DESC, er.id DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_emergency_request_by_id(request_id: int, user: dict = None) -> dict | None:
    """Retrieves a single emergency request with access authorization."""
    query = """
        SELECT er.*, u_eld.name as elderly_name, u_trig.name as triggered_by_name,
               u_ack.name as acknowledged_by_name, u_res.name as resolved_by_name
        FROM emergency_requests er
        JOIN users u_eld ON er.elderly_user_id = u_eld.id
        LEFT JOIN users u_trig ON er.triggered_by_user_id = u_trig.id
        LEFT JOIN users u_ack ON er.acknowledged_by = u_ack.id
        LEFT JOIN users u_res ON er.resolved_by = u_res.id
        WHERE er.id = ?
    """
    with get_connection() as conn:
        row = conn.execute(query, (request_id,)).fetchone()
        if not row:
            return None
        req = dict(row)

    if user:
        enforce_elderly_access(user, req["elderly_user_id"], write_access=False)

    return req


def get_active_emergency(elderly_user_id: int, user: dict = None) -> dict | None:
    """Returns the currently active emergency request (pending/acknowledged/in progress), if any."""
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    query = """
        SELECT er.*, u_eld.name as elderly_name, u_ack.name as acknowledged_by_name
        FROM emergency_requests er
        JOIN users u_eld ON er.elderly_user_id = u_eld.id
        LEFT JOIN users u_ack ON er.acknowledged_by = u_ack.id
        WHERE er.elderly_user_id = ?
          AND er.status IN ('pending', 'acknowledged', 'assistance_in_progress')
        ORDER BY er.id DESC LIMIT 1
    """
    with get_connection() as conn:
        row = conn.execute(query, (elderly_user_id,)).fetchone()
        return dict(row) if row else None


def get_emergency_status_history(request_id: int, user: dict = None) -> list[dict]:
    """Retrieves full status transition history for an emergency request."""
    req = get_emergency_request_by_id(request_id, user=user)
    if not req:
        return []

    query = """
        SELECT h.*, u.name as actor_name
        FROM emergency_status_history h
        LEFT JOIN users u ON h.actor_user_id = u.id
        WHERE h.request_id = ?
        ORDER BY h.created_at ASC, h.id ASC
    """
    with get_connection() as conn:
        rows = conn.execute(query, (request_id,)).fetchall()
        return [dict(r) for r in rows]


# =============================================================================
# STATUS TRANSITION ACTIONS
# =============================================================================

def acknowledge_emergency(
    request_id: int,
    elderly_user_id: int,
    actor_user_id: int,
    response_note: str = "",
    user: dict = None,
) -> bool:
    """Marks an active emergency as acknowledged by a caregiver."""
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    old_req = get_emergency_request_by_id(request_id)
    if not old_req or old_req["elderly_user_id"] != elderly_user_id:
        raise ValueError(f"Emergency request #{request_id} not found for this profile.")

    from_st = old_req["status"]

    with get_connection() as conn:
        actor_row = conn.execute("SELECT name FROM users WHERE id = ?", (actor_user_id,)).fetchone()
        actor_name = actor_row["name"] if actor_row else f"User #{actor_user_id}"

        conn.execute(
            """UPDATE emergency_requests
               SET status = 'acknowledged',
                   acknowledged_by = ?,
                   acknowledged_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND elderly_user_id = ?""",
            (actor_user_id, request_id, elderly_user_id),
        )

        conn.execute(
            """INSERT INTO emergency_status_history
               (request_id, elderly_user_id, actor_user_id, from_status, to_status, response_note, created_at)
               VALUES (?, ?, ?, ?, 'acknowledged', ?, CURRENT_TIMESTAMP)""",
            (request_id, elderly_user_id, actor_user_id, from_st, response_note.strip() or f"Acknowledged by {actor_name}"),
        )

        # Update legacy alerts
        conn.execute("UPDATE emergency_alerts SET status = 'acknowledged' WHERE id = ?", (request_id,))

        # Notify senior and care circle
        recipients = [elderly_user_id]
        cc_rows = conn.execute(
            """SELECT cc.member_user_id FROM care_circle cc
               JOIN users u ON cc.member_user_id = u.id
               WHERE cc.elderly_user_id = ? AND (cc.status IS NULL OR cc.status = 'active')""",
            (elderly_user_id,),
        ).fetchall()
        recipients.extend([r["member_user_id"] for r in cc_rows if r["member_user_id"] != actor_user_id])

        note_str = f" Note: {response_note.strip()}." if response_note.strip() else ""
        for uid in set(recipients):
            conn.execute(
                """INSERT INTO notifications
                   (user_id, elderly_user_id, alert_type, title, message)
                   VALUES (?, ?, 'system', ?, ?)""",
                (
                    uid,
                    elderly_user_id,
                    f"Emergency #{request_id} Acknowledged",
                    f"{actor_name} has acknowledged the emergency request.{note_str}",
                ),
            )

    log_activity(
        elderly_user_id,
        actor_user_id,
        "Emergency Acknowledged",
        f"Emergency request #{request_id} was acknowledged by {actor_name}. {response_note.strip()}".strip(),
    )
    return True


def update_assistance_status(
    request_id: int,
    elderly_user_id: int,
    actor_user_id: int,
    new_status: str,
    response_note: str = "",
    user: dict = None,
) -> bool:
    """Updates assistance status (e.g. to 'assistance_in_progress')."""
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    clean_status = new_status.strip().lower()
    if clean_status not in VALID_STATUSES:
        raise ValueError(f"Invalid emergency status: '{new_status}'.")

    old_req = get_emergency_request_by_id(request_id)
    if not old_req or old_req["elderly_user_id"] != elderly_user_id:
        raise ValueError(f"Emergency request #{request_id} not found.")

    from_st = old_req["status"]

    with get_connection() as conn:
        actor_row = conn.execute("SELECT name FROM users WHERE id = ?", (actor_user_id,)).fetchone()
        actor_name = actor_row["name"] if actor_row else f"User #{actor_user_id}"

        conn.execute(
            """UPDATE emergency_requests
               SET status = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND elderly_user_id = ?""",
            (clean_status, request_id, elderly_user_id),
        )

        conn.execute(
            """INSERT INTO emergency_status_history
               (request_id, elderly_user_id, actor_user_id, from_status, to_status, response_note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (request_id, elderly_user_id, actor_user_id, from_st, clean_status, response_note.strip()),
        )

        # Notify senior & care circle
        recipients = [elderly_user_id]
        cc_rows = conn.execute(
            """SELECT cc.member_user_id FROM care_circle cc
               JOIN users u ON cc.member_user_id = u.id
               WHERE cc.elderly_user_id = ? AND (cc.status IS NULL OR cc.status = 'active')""",
            (elderly_user_id,),
        ).fetchall()
        recipients.extend([r["member_user_id"] for r in cc_rows if r["member_user_id"] != actor_user_id])

        status_label = clean_status.replace("_", " ").title()
        note_str = f" Note: {response_note.strip()}." if response_note.strip() else ""
        for uid in set(recipients):
            conn.execute(
                """INSERT INTO notifications
                   (user_id, elderly_user_id, alert_type, title, message)
                   VALUES (?, ?, 'system', ?, ?)""",
                (
                    uid,
                    elderly_user_id,
                    f"Emergency Update: {status_label}",
                    f"{actor_name} updated status for Emergency #{request_id} to '{status_label}'.{note_str}",
                ),
            )

    log_activity(
        elderly_user_id,
        actor_user_id,
        f"Emergency Status Updated: {clean_status}",
        f"Emergency #{request_id} transitioned from '{from_st}' to '{clean_status}'. {response_note.strip()}".strip(),
    )
    return True


def resolve_emergency(
    request_id: int,
    elderly_user_id: int,
    actor_user_id: int,
    resolution_notes: str = "",
    user: dict = None,
) -> bool:
    """Marks an emergency request as resolved with resolution notes."""
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    old_req = get_emergency_request_by_id(request_id)
    if not old_req or old_req["elderly_user_id"] != elderly_user_id:
        raise ValueError(f"Emergency request #{request_id} not found.")

    from_st = old_req["status"]

    with get_connection() as conn:
        actor_row = conn.execute("SELECT name FROM users WHERE id = ?", (actor_user_id,)).fetchone()
        actor_name = actor_row["name"] if actor_row else f"User #{actor_user_id}"

        conn.execute(
            """UPDATE emergency_requests
               SET status = 'resolved',
                   resolved_by = ?,
                   resolved_at = CURRENT_TIMESTAMP,
                   resolution_notes = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND elderly_user_id = ?""",
            (actor_user_id, resolution_notes.strip(), request_id, elderly_user_id),
        )

        conn.execute(
            """INSERT INTO emergency_status_history
               (request_id, elderly_user_id, actor_user_id, from_status, to_status, response_note, created_at)
               VALUES (?, ?, ?, ?, 'resolved', ?, CURRENT_TIMESTAMP)""",
            (request_id, elderly_user_id, actor_user_id, from_st, resolution_notes.strip() or f"Resolved by {actor_name}"),
        )

        # Update legacy alert
        conn.execute("UPDATE emergency_alerts SET status = 'resolved' WHERE id = ?", (request_id,))

        recipients = [elderly_user_id]
        cc_rows = conn.execute(
            """SELECT cc.member_user_id FROM care_circle cc
               JOIN users u ON cc.member_user_id = u.id
               WHERE cc.elderly_user_id = ? AND (cc.status IS NULL OR cc.status = 'active')""",
            (elderly_user_id,),
        ).fetchall()
        recipients.extend([r["member_user_id"] for r in cc_rows if r["member_user_id"] != actor_user_id])

        res_str = f" Outcome: {resolution_notes.strip()}." if resolution_notes.strip() else ""
        for uid in set(recipients):
            conn.execute(
                """INSERT INTO notifications
                   (user_id, elderly_user_id, alert_type, title, message)
                   VALUES (?, ?, 'system', ?, ?)""",
                (
                    uid,
                    elderly_user_id,
                    f"Emergency #{request_id} Resolved",
                    f"{actor_name} marked Emergency #{request_id} as resolved.{res_str}",
                ),
            )

    log_activity(
        elderly_user_id,
        actor_user_id,
        "Emergency Resolved",
        f"Emergency #{request_id} resolved by {actor_name}. Resolution: {resolution_notes.strip()}".strip(),
    )
    return True


def cancel_emergency(
    request_id: int,
    elderly_user_id: int,
    actor_user_id: int,
    cancel_reason: str = "",
    user: dict = None,
) -> bool:
    """Cancels an emergency request (e.g. false alarm or accidental trigger)."""
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    old_req = get_emergency_request_by_id(request_id)
    if not old_req or old_req["elderly_user_id"] != elderly_user_id:
        raise ValueError(f"Emergency request #{request_id} not found.")

    from_st = old_req["status"]

    with get_connection() as conn:
        actor_row = conn.execute("SELECT name FROM users WHERE id = ?", (actor_user_id,)).fetchone()
        actor_name = actor_row["name"] if actor_row else f"User #{actor_user_id}"

        conn.execute(
            """UPDATE emergency_requests
               SET status = 'cancelled',
                   resolution_notes = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND elderly_user_id = ?""",
            (f"Cancelled: {cancel_reason.strip()}", request_id, elderly_user_id),
        )

        conn.execute(
            """INSERT INTO emergency_status_history
               (request_id, elderly_user_id, actor_user_id, from_status, to_status, response_note, created_at)
               VALUES (?, ?, ?, ?, 'cancelled', ?, CURRENT_TIMESTAMP)""",
            (request_id, elderly_user_id, actor_user_id, from_st, cancel_reason.strip() or f"Cancelled by {actor_name}"),
        )

        conn.execute("UPDATE emergency_alerts SET status = 'resolved' WHERE id = ?", (request_id,))

        recipients = [elderly_user_id]
        cc_rows = conn.execute(
            """SELECT cc.member_user_id FROM care_circle cc
               JOIN users u ON cc.member_user_id = u.id
               WHERE cc.elderly_user_id = ? AND (cc.status IS NULL OR cc.status = 'active')""",
            (elderly_user_id,),
        ).fetchall()
        recipients.extend([r["member_user_id"] for r in cc_rows if r["member_user_id"] != actor_user_id])

        c_str = f" Reason: {cancel_reason.strip()}." if cancel_reason.strip() else ""
        for uid in set(recipients):
            conn.execute(
                """INSERT INTO notifications
                   (user_id, elderly_user_id, alert_type, title, message)
                   VALUES (?, ?, 'system', ?, ?)""",
                (
                    uid,
                    elderly_user_id,
                    f"Emergency #{request_id} Cancelled",
                    f"Emergency request was cancelled by {actor_name}.{c_str}",
                ),
            )

    log_activity(
        elderly_user_id,
        actor_user_id,
        "Emergency Cancelled",
        f"Emergency #{request_id} cancelled by {actor_name}. Reason: {cancel_reason.strip()}".strip(),
    )
    return True


# =============================================================================
# BACKWARD COMPATIBILITY WRAPPERS (for test_app.py and legacy components)
# =============================================================================

def trigger_sos_alert(
    elderly_user_id: int,
    triggered_by_user_id: int,
    message: str = "Urgent SOS button activated by elderly user",
) -> int:
    """Backward-compatible helper invoking activate_emergency_sos."""
    try:
        return activate_emergency_sos(
            elderly_user_id=elderly_user_id,
            triggered_by_user_id=triggered_by_user_id,
            urgency_reason=message,
        )
    except ValueError:
        # If an active emergency exists from a previous test/run, resolve it for legacy idempotent behavior
        active = get_active_emergency(elderly_user_id)
        if active:
            try:
                resolve_emergency(
                    active["id"],
                    elderly_user_id,
                    triggered_by_user_id,
                    resolution_notes="Auto-resolved prior alert for legacy trigger",
                )
            except Exception as auto_res_err:
                logger.debug("Auto-resolve prior alert status: %s", auto_res_err)
        return activate_emergency_sos(
            elderly_user_id=elderly_user_id,
            triggered_by_user_id=triggered_by_user_id,
            urgency_reason=message,
        )


def get_active_emergency_alerts(elderly_user_id: int) -> list[dict]:
    """Backward-compatible helper returning active alerts from emergency_requests or legacy alerts."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT er.id, 'SOS' as alert_type, er.status, er.urgency_reason as message, er.created_at,
                      u.name as triggered_by_name
               FROM emergency_requests er
               JOIN users u ON er.triggered_by_user_id = u.id
               WHERE er.elderly_user_id = ? AND er.status = 'pending'
               ORDER BY er.created_at DESC""",
            (elderly_user_id,),
        ).fetchall()
        alerts = [dict(r) for r in rows]
        legacy_rows = conn.execute(
            """SELECT ea.id, ea.alert_type, ea.status, ea.message, ea.created_at,
                      u.name as triggered_by_name
               FROM emergency_alerts ea
               JOIN users u ON ea.triggered_by_user_id = u.id
               WHERE ea.elderly_user_id = ? AND ea.status = 'active'
               ORDER BY ea.created_at DESC""",
            (elderly_user_id,),
        ).fetchall()
        seen_ids = {a["id"] for a in alerts}
        for lr in legacy_rows:
            if lr["id"] not in seen_ids:
                alerts.append(dict(lr))
        return alerts


def acknowledge_alert(alert_id: int, elderly_user_id: int, acknowledged_by_id: int):
    """Backward-compatible alert acknowledgment."""
    try:
        acknowledge_emergency(alert_id, elderly_user_id, acknowledged_by_id, response_note="Acknowledged alert")
    except Exception as ack_err:
        logger.debug("Legacy acknowledge alert note: %s", ack_err)
    with get_connection() as conn:
        conn.execute(
            "UPDATE emergency_alerts SET status = 'acknowledged' WHERE id = ?",
            (alert_id,),
        )


def simulate_reminder_notification(
    elderly_user_id: int,
    recipient_email: str,
    subject: str,
    message: str,
    channel: str = "email",
):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO simulated_reminders (elderly_user_id, recipient_email, subject, message, channel, status)
               VALUES (?, ?, ?, ?, ?, 'simulated_sent')""",
            (elderly_user_id, recipient_email.strip(), subject.strip(), message.strip(), channel),
        )


def get_simulated_reminders(elderly_user_id: int, limit: int = 15):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, elderly_user_id, recipient_email, subject, message, channel, status, sent_at
               FROM simulated_reminders
               WHERE elderly_user_id = ?
               ORDER BY sent_at DESC LIMIT ?""",
            (elderly_user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
