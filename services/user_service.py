import re
import sqlite3
from datetime import datetime
from database import get_connection, hash_password
from services.activity_service import log_activity

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def validate_registration_input(
    name: str,
    email: str,
    phone: str,
    password: str,
    confirm_password: str,
    role: str,
):
    """Validates registration inputs and returns (is_valid, error_message)."""
    if not name or len(name.strip()) < 2:
        return False, "Full name must be at least 2 characters."

    if not email or not EMAIL_REGEX.match(email.strip()):
        return False, "Please enter a valid email address."

    digits_only = re.sub(r"[^\d]", "", phone.strip()) if phone else ""
    if not digits_only or len(digits_only) < 7:
        return False, "Please enter a valid phone number with at least 7 digits."

    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters long."

    if password != confirm_password:
        return False, "Passwords do not match. Please re-enter."

    if role not in ("elderly", "caregiver", "family"):
        return False, f"Invalid account role '{role}'. Must be Elderly, Caregiver, or Family."

    return True, ""

def register_user(
    name: str,
    email: str,
    phone: str,
    password: str,
    confirm_password: str,
    role: str,
):
    """
    Registers a new user into SQLite with bcrypt password hashing.
    Returns (success: bool, user_or_message: dict | str).
    """
    is_valid, err_msg = validate_registration_input(
        name=name,
        email=email,
        phone=phone,
        password=password,
        confirm_password=confirm_password,
        role=role,
    )
    if not is_valid:
        return False, err_msg

    clean_email = email.strip().lower()
    clean_name = name.strip()
    clean_phone = phone.strip()

    with get_connection() as conn:
        # Check for existing email (case-insensitive)
        existing = conn.execute(
            "SELECT id FROM users WHERE LOWER(email) = LOWER(?)",
            (clean_email,),
        ).fetchone()
        if existing:
            return False, f"An account with email '{clean_email}' already exists. Please sign in or use another email."

        # Generate secure bcrypt password hash
        pw_hash = hash_password(password)

        cursor = conn.execute(
            """INSERT INTO users (name, email, password_hash, role, phone, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (clean_name, clean_email, pw_hash, role, clean_phone),
        )
        user_id = cursor.lastrowid

        # If elderly role, create initial profile entry
        if role == "elderly":
            conn.execute(
                """INSERT OR IGNORE INTO elderly_profiles (user_id, notes)
                   VALUES (?, 'Newly registered elderly account')""",
                (user_id,),
            )

    log_activity(
        elderly_user_id=user_id if role == "elderly" else 1,
        actor_user_id=user_id,
        action="User Registered",
        details=f"Account created for {clean_name} ({clean_email}) as {role.title()}",
    )

    new_user = {
        "id": user_id,
        "name": clean_name,
        "email": clean_email,
        "phone": clean_phone,
        "role": role,
    }
    return True, new_user

def get_user_profile(user_id: int):
    """Retrieves safe user profile dictionary (excluding password hash)."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT id, name, email, phone, role, created_at, updated_at
               FROM users WHERE id = ?""",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None

def update_user_profile(user_id: int, name: str, phone: str):
    """
    Updates user's full name and phone number.
    Role cannot be changed through profile editing.
    Returns (success: bool, message: str).
    """
    if not name or len(name.strip()) < 2:
        return False, "Full name must be at least 2 characters."

    digits_only = re.sub(r"[^\d]", "", phone.strip()) if phone else ""
    if not digits_only or len(digits_only) < 7:
        return False, "Please enter a valid phone number with at least 7 digits."

    clean_name = name.strip()
    clean_phone = phone.strip()
    with get_connection() as conn:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """UPDATE users
               SET name = ?, phone = ?, updated_at = ?
               WHERE id = ?""",
            (clean_name, clean_phone, now_str, user_id),
        )

    return True, "Profile details updated successfully."
