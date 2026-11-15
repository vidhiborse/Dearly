import sqlite3
from database import get_connection
from services.activity_service import log_activity

def get_elderly_profile(elderly_user_id: int):
    with get_connection() as conn:
        row = conn.execute(
            """SELECT u.id, u.name, u.email, u.phone, ep.date_of_birth, ep.blood_group,
                      ep.emergency_contact, ep.allergies, ep.primary_physician, ep.primary_physician_phone, ep.notes
               FROM users u
               LEFT JOIN elderly_profiles ep ON ep.user_id = u.id
               WHERE u.id = ?""",
            (elderly_user_id,),
        ).fetchone()
        return dict(row) if row else None

def update_elderly_profile(
    elderly_user_id: int,
    phone: str,
    date_of_birth: str,
    blood_group: str,
    emergency_contact: str,
    allergies: str,
    primary_physician: str,
    primary_physician_phone: str,
    notes: str,
    updated_by: int = None,
):
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET phone = ? WHERE id = ?",
            (phone.strip(), elderly_user_id),
        )
        conn.execute(
            """INSERT INTO elderly_profiles
               (user_id, date_of_birth, blood_group, emergency_contact, allergies, primary_physician, primary_physician_phone, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   date_of_birth = excluded.date_of_birth,
                   blood_group = excluded.blood_group,
                   emergency_contact = excluded.emergency_contact,
                   allergies = excluded.allergies,
                   primary_physician = excluded.primary_physician,
                   primary_physician_phone = excluded.primary_physician_phone,
                   notes = excluded.notes""",
            (elderly_user_id, date_of_birth.strip(), blood_group.strip(), emergency_contact.strip(), allergies.strip(), primary_physician.strip(), primary_physician_phone.strip(), notes.strip()),
        )

    if updated_by:
        log_activity(
            elderly_user_id,
            updated_by,
            "Updated Medical Profile",
            "Emergency contact, physician details, or health profile information updated",
        )

def get_care_circle_members(elderly_user_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT cc.id as link_id, cc.relationship, cc.permission_level, cc.created_at,
                      u.id as user_id, u.name, u.email, u.phone, u.role
               FROM care_circle cc
               JOIN users u ON cc.member_user_id = u.id
               WHERE cc.elderly_user_id = ?
               ORDER BY cc.permission_level DESC, u.name ASC""",
            (elderly_user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

def add_care_circle_member(
    elderly_user_id: int,
    email: str,
    relationship: str,
    permission_level: str = "viewer",
    added_by: int = None,
):
    with get_connection() as conn:
        target_user = conn.execute("SELECT id, name, role FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        if not target_user:
            return False, "No registered account found with that email. Make sure your family member or caregiver has registered first."

        if target_user["id"] == elderly_user_id:
            return False, "Cannot add the elderly individual as a member of their own circle."

        conn.execute(
            """INSERT OR REPLACE INTO care_circle
               (elderly_user_id, member_user_id, relationship, permission_level)
               VALUES (?, ?, ?, ?)""",
            (elderly_user_id, target_user["id"], relationship.strip(), permission_level),
        )

    if added_by:
        log_activity(
            elderly_user_id,
            added_by,
            "Added Care Circle Member",
            f"Added {target_user['name']} as {relationship} with {permission_level} permission",
        )
    return True, f"Successfully linked {target_user['name']} to the care circle."

def remove_care_circle_member(elderly_user_id: int, member_user_id: int, removed_by: int = None):
    with get_connection() as conn:
        u = conn.execute("SELECT name FROM users WHERE id = ?", (member_user_id,)).fetchone()
        name = u["name"] if u else "Member"
        conn.execute(
            "DELETE FROM care_circle WHERE elderly_user_id = ? AND member_user_id = ?",
            (elderly_user_id, member_user_id),
        )

    if removed_by:
        log_activity(
            elderly_user_id,
            removed_by,
            "Removed Care Circle Member",
            f"Removed {name} from care circle",
        )

def check_permission(elderly_user_id: int, user: dict, required_level: str = "viewer") -> bool:
    if not user:
        return False
    if user["id"] == elderly_user_id:
        return True
    if user["role"] == "caregiver":
        return True
    with get_connection() as conn:
        row = conn.execute(
            "SELECT permission_level FROM care_circle WHERE elderly_user_id = ? AND member_user_id = ?",
            (elderly_user_id, user["id"]),
        ).fetchone()
        if not row:
            return False
        if required_level == "viewer":
            return True
        return row["permission_level"] == "editor"
