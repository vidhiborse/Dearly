import sqlite3
from database import get_connection, authenticate_user, authenticate_with_passcode
from services.permissions import can_access_elderly_record

def authenticate(email: str, password: str):
    """Authenticates email and password using secure bcrypt hash verification."""
    return authenticate_user(email, password)

def authenticate_passcode(passcode: str):
    """
    Direct passcode / PIN authentication designed specifically for elderly accessibility.
    Allows seniors and care circle members to access their profile securely using a numeric PIN.
    """
    return authenticate_with_passcode(passcode)

def get_user_by_id(user_id: int):
    with get_connection() as conn:
        user = conn.execute(
            "SELECT id, name, email, role, phone, created_at, updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(user) if user else None

def get_accessible_elderly_wards(user: dict):
    """
    Returns list of elderly users that the current user is permitted to view/manage.
    Strictly enforces authorization:
    - Elderly user: returns only self.
    - Caregiver / Family: returns only members linked in care_circle.
    """
    if not user:
        return []

    with get_connection() as conn:
        if user["role"] == "elderly":
            elderly = conn.execute(
                """SELECT u.id, u.name, u.email, u.phone, ep.date_of_birth, ep.blood_group, 
                          ep.emergency_contact, ep.allergies, ep.primary_physician, ep.primary_physician_phone, ep.notes
                   FROM users u
                   LEFT JOIN elderly_profiles ep ON ep.user_id = u.id
                   WHERE u.id = ?""",
                (user["id"],),
            ).fetchone()
            return [dict(elderly)] if elderly else []
        else:
            rows = conn.execute(
                """SELECT u.id, u.name, u.email, u.phone, cc.relationship, cc.permission_level,
                          ep.date_of_birth, ep.blood_group, ep.emergency_contact, ep.allergies,
                          ep.primary_physician, ep.primary_physician_phone, ep.notes
                   FROM care_circle cc
                   JOIN users u ON cc.elderly_user_id = u.id
                   LEFT JOIN elderly_profiles ep ON ep.user_id = u.id
                   WHERE cc.member_user_id = ?
                     AND (cc.status IS NULL OR cc.status = 'active')
                   ORDER BY u.name ASC""",
                (user["id"],),
            ).fetchall()
            return [dict(r) for r in rows]
