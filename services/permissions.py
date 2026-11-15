from database import get_connection

def can_access_elderly_record(user: dict, elderly_user_id: int) -> bool:
    """
    Checks if user is authorized to view an elderly individual's care record:
    - Elderly individual: permitted ONLY for their own record.
    - Caregiver or Family: permitted ONLY if explicitly linked in care_circle.
    """
    if not user or not elderly_user_id:
        return False

    try:
        user_id = int(user["id"])
        e_user_id = int(elderly_user_id)
    except (ValueError, TypeError, KeyError):
        return False

    role = user.get("role", "")

    # An elderly user can only access their own record
    if role == "elderly":
        return user_id == e_user_id

    # Caregivers and Family must be linked in care_circle
    with get_connection() as conn:
        link = conn.execute(
            """SELECT id, permission_level
               FROM care_circle
               WHERE elderly_user_id = ? AND member_user_id = ?""",
            (e_user_id, user_id),
        ).fetchone()
        return link is not None

def can_manage_elderly_care(user: dict, elderly_user_id: int) -> bool:
    """
    Checks if user is authorized to perform write/management actions (meds, appointments, vitals):
    - Elderly individual: permitted for their own routine.
    - Caregiver: permitted if linked with 'editor' permission in care_circle.
    - Family: DENIED by default unless explicitly granted 'editor' permission.
    """
    if not user or not elderly_user_id:
        return False

    try:
        user_id = int(user["id"])
        e_user_id = int(elderly_user_id)
    except (ValueError, TypeError, KeyError):
        return False

    role = user.get("role", "")

    # Self-management for elderly user
    if role == "elderly":
        return user_id == e_user_id

    with get_connection() as conn:
        link = conn.execute(
            """SELECT permission_level
               FROM care_circle
               WHERE elderly_user_id = ? AND member_user_id = ?""",
            (e_user_id, user_id),
        ).fetchone()
        if not link:
            return False
        return link["permission_level"] == "editor"

def can_view_page(user: dict, requested_page: str) -> bool:
    """Enforces role-based page whitelist."""
    if not user:
        return False

    role = user.get("role", "")
    allowed_pages = {
        "elderly": ["Home", "My Medicines", "Reminders & Alerts", "Appointments", "My Health", "Emergency Contacts", "My Profile"],
        "caregiver": ["Overview", "Reminders & Alerts", "Elderly Profiles", "Medication Monitoring", "Appointments", "Health Records", "Activity History", "My Profile"],
        "family": ["Overview", "Reminders & Alerts", "Care Updates", "Medicines", "Appointments", "Health Summary", "My Profile"],
    }
    return requested_page in allowed_pages.get(role, [])

def enforce_elderly_access(user: dict, elderly_user_id: int, write_access: bool = False):
    """
    Backend guard: raises PermissionError if the current user is unauthorized.
    Protects API / service operations from unauthorized parameter tampering.
    """
    if write_access:
        if not can_manage_elderly_care(user, elderly_user_id):
            raise PermissionError(f"User #{user.get('id')} lacks write permissions for elderly record #{elderly_user_id}")
    else:
        if not can_access_elderly_record(user, elderly_user_id):
            raise PermissionError(f"User #{user.get('id')} is not authorized to access elderly record #{elderly_user_id}")
