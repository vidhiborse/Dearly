import sqlite3
from datetime import datetime, date
from database import get_connection
from services.activity_service import log_activity
from services.permissions import (
    can_access_elderly_record,
    can_manage_care_circle,
    enforce_elderly_access,
)


def get_elderly_profile(elderly_user_id: int) -> dict | None:
    """Fetches medical and clinical profile of an elderly individual."""
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
    """Updates contact information and clinical parameters for an elderly profile."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET phone = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
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
            (
                elderly_user_id,
                date_of_birth.strip(),
                blood_group.strip(),
                emergency_contact.strip(),
                allergies.strip(),
                primary_physician.strip(),
                primary_physician_phone.strip(),
                notes.strip(),
            ),
        )

    if updated_by:
        log_activity(
            elderly_user_id,
            updated_by,
            "Updated Medical Profile",
            "Emergency contact, physician details, or health profile information updated",
        )


def get_care_circle_members(elderly_user_id: int, user: dict = None) -> list[dict]:
    """
    Returns active members of an elderly user's care circle.
    Enforces server-side read authorization when user is provided.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT cc.id as link_id, cc.relationship, cc.permission_level,
                      COALESCE(cc.connection_role, u.role) as connection_role,
                      COALESCE(cc.status, 'active') as status,
                      COALESCE(cc.is_primary, 0) as is_primary,
                      cc.created_at, cc.created_by,
                      u.id as user_id, u.name, u.email, u.phone, u.role as user_role,
                      u_creator.name as created_by_name
               FROM care_circle cc
               JOIN users u ON cc.member_user_id = u.id
               LEFT JOIN users u_creator ON cc.created_by = u_creator.id
               WHERE cc.elderly_user_id = ? AND (cc.status IS NULL OR cc.status = 'active')
               ORDER BY cc.is_primary DESC, cc.permission_level DESC, u.name ASC""",
            (elderly_user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_care_circle_dashboard(elderly_user_id: int, user: dict = None) -> dict:
    """
    Returns structured care circle overview:
    - Elderly person details
    - Primary caregiver
    - Other caregivers
    - Family members
    - Pending invitations
    - Summary counts
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    profile = get_elderly_profile(elderly_user_id)
    all_members = get_care_circle_members(elderly_user_id, user=user)

    primary_cg = None
    caregivers = []
    family_members = []

    for m in all_members:
        if m.get("is_primary") == 1:
            primary_cg = m
        if m.get("connection_role") == "caregiver" or m.get("user_role") == "caregiver":
            caregivers.append(m)
        else:
            family_members.append(m)

    pending_invites = get_elderly_pending_invitations(elderly_user_id, user=user)

    return {
        "elderly_profile": profile,
        "primary_caregiver": primary_cg,
        "caregivers": caregivers,
        "family_members": family_members,
        "pending_invitations": pending_invites,
        "counts": {
            "total_active": len(all_members),
            "caregivers_count": len(caregivers),
            "family_count": len(family_members),
            "pending_count": len(pending_invites),
        },
    }


def send_care_invitation(
    elderly_user_id: int,
    inviter_user: dict,
    invitee_email: str,
    relationship: str,
    connection_role: str,
    permission_level: str = "viewer",
) -> tuple[bool, str, int | None]:
    """
    Invites an existing registered user to join an elderly person's care circle.
    Validates account existence, role, permission level, and duplicate avoidance.
    Enforces server-side authorization.
    """
    if not inviter_user:
        return False, "Authentication required.", None

    if not can_manage_care_circle(inviter_user, elderly_user_id):
        raise PermissionError(f"User #{inviter_user.get('id')} lacks permission to send care circle invitations for profile #{elderly_user_id}")

    clean_email = invitee_email.strip().lower()
    if not clean_email:
        return False, "Please provide an email address.", None

    clean_rel = relationship.strip()
    if len(clean_rel) < 2:
        return False, "Please specify a relationship.", None

    clean_role = connection_role.strip().lower()
    if clean_role not in ("caregiver", "family"):
        return False, "Connection role must be 'caregiver' or 'family'.", None

    clean_perm = permission_level.strip().lower()
    if clean_perm not in ("editor", "viewer"):
        return False, "Permission level must be 'editor' or 'viewer'.", None

    with get_connection() as conn:
        # Check elderly person exists
        eld_row = conn.execute("SELECT id, name FROM users WHERE id = ?", (elderly_user_id,)).fetchone()
        if not eld_row:
            return False, "Elderly profile not found.", None
        elderly_name = eld_row["name"]

        # 1. Verify invitee account exists
        target_row = conn.execute(
            "SELECT id, name, email, role FROM users WHERE LOWER(email) = ?",
            (clean_email,),
        ).fetchone()
        if not target_row:
            return False, "No registered account found with that email address. The recipient must register on Dearly first.", None

        target_id = target_row["id"]
        target_name = target_row["name"]

        # 2. Prevent self-invitation
        if target_id == inviter_user["id"]:
            return False, "You cannot send a care circle invitation to yourself.", None

        if target_id == elderly_user_id:
            return False, "Cannot invite the elderly person to their own care circle.", None

        # 3. Check if already an active member
        existing_member = conn.execute(
            "SELECT id, permission_level FROM care_circle WHERE elderly_user_id = ? AND member_user_id = ? AND status = 'active'",
            (elderly_user_id, target_id),
        ).fetchone()
        if existing_member:
            return False, f"{target_name} is already an active member of this care circle.", None

        # 4. Check for existing pending invitation
        existing_invite = conn.execute(
            """SELECT id FROM care_invitations
               WHERE elderly_user_id = ? AND LOWER(invitee_email) = ? AND status = 'pending'""",
            (elderly_user_id, clean_email),
        ).fetchone()
        if existing_invite:
            return False, f"A pending invitation for {clean_email} already exists.", None

        # 5. Create pending invitation
        cursor = conn.execute(
            """INSERT INTO care_invitations
               (elderly_user_id, inviter_user_id, invitee_email, invitee_user_id, relationship, connection_role, permission_level, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (elderly_user_id, inviter_user["id"], clean_email, target_id, clean_rel, clean_role, clean_perm),
        )
        invitation_id = cursor.lastrowid

        # 6. Dispatch in-app notification to invitee
        role_label = "Caregiver" if clean_role == "caregiver" else "Family Member"
        conn.execute(
            """INSERT INTO notifications
               (user_id, elderly_user_id, alert_type, title, message)
               VALUES (?, ?, 'system', ?, ?)""",
            (
                target_id,
                elderly_user_id,
                f"Care Circle Invitation: {elderly_name}",
                f"{inviter_user['name']} has invited you to join the care circle for {elderly_name} as {clean_rel} ({role_label} with {clean_perm.title()} access). Check Care Circle to accept or decline.",
            ),
        )

    log_activity(
        elderly_user_id,
        inviter_user["id"],
        "Sent Care Circle Invitation",
        f"Invited {target_name} ({clean_email}) as {clean_rel} ({clean_role}, {clean_perm} permission)",
    )

    return True, f"Invitation sent successfully to {target_name} ({clean_email}).", invitation_id


def get_user_pending_invitations(user: dict) -> list[dict]:
    """
    Returns pending care circle invitations received by the current user.
    """
    if not user:
        return []

    clean_email = user["email"].strip().lower()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT ci.id, ci.elderly_user_id, ci.inviter_user_id, ci.invitee_email,
                      ci.relationship, ci.connection_role, ci.permission_level, ci.status, ci.created_at,
                      u_eld.name as elderly_name, u_inv.name as inviter_name
               FROM care_invitations ci
               JOIN users u_eld ON ci.elderly_user_id = u_eld.id
               JOIN users u_inv ON ci.inviter_user_id = u_inv.id
               WHERE LOWER(ci.invitee_email) = ? AND ci.status = 'pending'
               ORDER BY ci.created_at DESC""",
            (clean_email,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_elderly_pending_invitations(elderly_user_id: int, user: dict = None) -> list[dict]:
    """
    Returns pending invitations dispatched for this elderly individual.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT ci.id, ci.elderly_user_id, ci.inviter_user_id, ci.invitee_email,
                      ci.relationship, ci.connection_role, ci.permission_level, ci.status, ci.created_at,
                      u_inv.name as inviter_name,
                      COALESCE(u_tgt.name, ci.invitee_email) as invitee_name
               FROM care_invitations ci
               JOIN users u_inv ON ci.inviter_user_id = u_inv.id
               LEFT JOIN users u_tgt ON LOWER(ci.invitee_email) = LOWER(u_tgt.email)
               WHERE ci.elderly_user_id = ? AND ci.status = 'pending'
               ORDER BY ci.created_at DESC""",
            (elderly_user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def respond_to_invitation(invitation_id: int, user: dict, action: str) -> tuple[bool, str]:
    """
    Accepts or rejects a pending care circle invitation.
    - If accepted: creates/activates care_circle link with specified permissions.
    - If rejected: updates invitation status to 'rejected' without granting any access.
    - Emits in-app notifications and audit logs.
    """
    if not user:
        return False, "Authentication required."

    action_clean = action.strip().lower()
    if action_clean not in ("accept", "reject"):
        return False, "Action must be 'accept' or 'reject'."

    clean_email = user["email"].strip().lower()

    with get_connection() as conn:
        invite = conn.execute(
            """SELECT ci.id, ci.elderly_user_id, ci.inviter_user_id, ci.invitee_email,
                      ci.relationship, ci.connection_role, ci.permission_level, ci.status,
                      u_eld.name as elderly_name, u_inv.name as inviter_name
               FROM care_invitations ci
               JOIN users u_eld ON ci.elderly_user_id = u_eld.id
               JOIN users u_inv ON ci.inviter_user_id = u_inv.id
               WHERE ci.id = ?""",
            (invitation_id,),
        ).fetchone()

        if not invite:
            return False, "Invitation not found."

        if invite["status"] != "pending":
            return False, f"This invitation is already {invite['status']}."

        if invite["invitee_email"].strip().lower() != clean_email:
            return False, "You are not authorized to respond to this invitation."

        elderly_id = invite["elderly_user_id"]
        inviter_id = invite["inviter_user_id"]
        elderly_name = invite["elderly_name"]
        relationship = invite["relationship"]
        connection_role = invite["connection_role"]
        permission_level = invite["permission_level"]

        if action_clean == "accept":
            # 1. Update invitation
            conn.execute(
                """UPDATE care_invitations
                   SET status = 'accepted', responded_at = CURRENT_TIMESTAMP, invitee_user_id = ?
                   WHERE id = ?""",
                (user["id"], invitation_id),
            )

            # 2. Insert into care_circle
            conn.execute(
                """INSERT INTO care_circle
                   (elderly_user_id, member_user_id, relationship, permission_level, connection_role, status, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, 'active', ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(elderly_user_id, member_user_id) DO UPDATE SET
                       relationship = excluded.relationship,
                       permission_level = excluded.permission_level,
                       connection_role = excluded.connection_role,
                       status = 'active',
                       created_by = excluded.created_by,
                       updated_at = CURRENT_TIMESTAMP""",
                (elderly_id, user["id"], relationship, permission_level, connection_role, inviter_id),
            )

            # 3. Notify inviter
            conn.execute(
                """INSERT INTO notifications
                   (user_id, elderly_user_id, alert_type, title, message)
                   VALUES (?, ?, 'system', ?, ?)""",
                (
                    inviter_id,
                    elderly_id,
                    "Care Circle Invitation Accepted",
                    f"{user['name']} has accepted the invitation and joined {elderly_name}'s care circle as {relationship}.",
                ),
            )

            # 4. Notify elderly user if different from inviter
            if elderly_id != inviter_id:
                conn.execute(
                    """INSERT INTO notifications
                       (user_id, elderly_user_id, alert_type, title, message)
                       VALUES (?, ?, 'system', ?, ?)""",
                    (
                        elderly_id,
                        elderly_id,
                        "New Care Circle Member Joined",
                        f"{user['name']} has joined your care circle as {relationship} ({connection_role.title()}).",
                    ),
                )

        else:  # reject
            conn.execute(
                """UPDATE care_invitations
                   SET status = 'rejected', responded_at = CURRENT_TIMESTAMP, invitee_user_id = ?
                   WHERE id = ?""",
                (user["id"], invitation_id),
            )

            # Notify inviter of decline
            conn.execute(
                """INSERT INTO notifications
                   (user_id, elderly_user_id, alert_type, title, message)
                   VALUES (?, ?, 'system', ?, ?)""",
                (
                    inviter_id,
                    elderly_id,
                    "Care Circle Invitation Declined",
                    f"{user['name']} declined the invitation to join {elderly_name}'s care circle.",
                ),
            )

    action_label = "Accepted Care Circle Invitation" if action_clean == "accept" else "Declined Care Circle Invitation"
    details_str = f"{user['name']} accepted invitation as {relationship}" if action_clean == "accept" else f"{user['name']} declined invitation"
    log_activity(elderly_id, user["id"], action_label, details_str)

    msg = f"You have accepted the invitation and joined {elderly_name}'s care circle." if action_clean == "accept" else "Invitation declined."
    return True, msg


def revoke_invitation(invitation_id: int, user: dict) -> tuple[bool, str]:
    """Allows an authorized inviter or elderly user to revoke/cancel a pending invitation."""
    if not user:
        return False, "Authentication required."

    with get_connection() as conn:
        invite = conn.execute(
            "SELECT id, elderly_user_id, inviter_user_id, invitee_email, status FROM care_invitations WHERE id = ?",
            (invitation_id,),
        ).fetchone()

        if not invite:
            return False, "Invitation not found."

        if invite["status"] != "pending":
            return False, f"Cannot revoke an invitation that is already {invite['status']}."

        # Permission check: must be elderly user or inviter or authorized editor
        elderly_id = invite["elderly_user_id"]
        if user["id"] != invite["inviter_user_id"] and not can_manage_care_circle(user, elderly_id):
            raise PermissionError("Unauthorized to revoke this invitation.")

        conn.execute(
            "UPDATE care_invitations SET status = 'revoked', responded_at = CURRENT_TIMESTAMP WHERE id = ?",
            (invitation_id,),
        )

    log_activity(elderly_id, user["id"], "Revoked Care Circle Invitation", f"Revoked invitation sent to {invite['invitee_email']}")
    return True, "Invitation revoked."


def remove_care_circle_member(elderly_user_id: int, member_user_id: int, actor_user: dict) -> tuple[bool, str]:
    """
    Removes a member from an elderly individual's care circle.
    Enforces server-side permissions:
    - Elderly individual can remove anyone.
    - Editor caregiver can remove other members (except cannot remove elderly person).
    - Family member (viewer) cannot remove members.
    Handles safe unassignment if member was primary caregiver.
    Dispatches in-app notification to the removed member.
    """
    if not actor_user:
        return False, "Authentication required."

    if not can_manage_care_circle(actor_user, elderly_user_id):
        raise PermissionError(f"User #{actor_user.get('id')} lacks permission to remove members from care circle #{elderly_user_id}")

    if member_user_id == elderly_user_id:
        return False, "Cannot remove the elderly individual from their own care circle."

    with get_connection() as conn:
        # Check target member exists in circle
        link = conn.execute(
            """SELECT cc.id, cc.relationship, cc.is_primary, u.name, u_eld.name as elderly_name
               FROM care_circle cc
               JOIN users u ON cc.member_user_id = u.id
               JOIN users u_eld ON cc.elderly_user_id = u_eld.id
               WHERE cc.elderly_user_id = ? AND cc.member_user_id = ? AND cc.status = 'active'""",
            (elderly_user_id, member_user_id),
        ).fetchone()

        if not link:
            return False, "Member not found in this care circle or already removed."

        member_name = link["name"]
        elderly_name = link["elderly_name"]

        # Delete record (or set status = 'removed')
        conn.execute(
            "DELETE FROM care_circle WHERE elderly_user_id = ? AND member_user_id = ?",
            (elderly_user_id, member_user_id),
        )

        # Notify removed user
        conn.execute(
            """INSERT INTO notifications
               (user_id, elderly_user_id, alert_type, title, message)
               VALUES (?, ?, 'system', ?, ?)""",
            (
                member_user_id,
                elderly_user_id,
                "Care Circle Connection Removed",
                f"Your connection to {elderly_name}'s care circle has been removed by {actor_user['name']}.",
            ),
        )

    log_activity(
        elderly_user_id,
        actor_user["id"],
        "Removed Care Circle Member",
        f"Removed {member_name} from care circle",
    )
    return True, f"Successfully removed {member_name} from the care circle."


def set_primary_caregiver(elderly_user_id: int, caregiver_user_id: int, actor_user: dict) -> tuple[bool, str]:
    """
    Designates a caregiver as the primary caregiver for an elderly profile.
    Enforces the single-primary rule: resets any existing primary designation and assigns to the selected caregiver.
    """
    if not actor_user:
        return False, "Authentication required."

    if not can_manage_care_circle(actor_user, elderly_user_id):
        raise PermissionError(f"User #{actor_user.get('id')} lacks permission to assign primary caregiver for profile #{elderly_user_id}")

    with get_connection() as conn:
        # Verify target is an active caregiver in the circle
        member = conn.execute(
            """SELECT cc.id, u.name, cc.connection_role, u.role
               FROM care_circle cc
               JOIN users u ON cc.member_user_id = u.id
               WHERE cc.elderly_user_id = ? AND cc.member_user_id = ? AND cc.status = 'active'""",
            (elderly_user_id, caregiver_user_id),
        ).fetchone()

        if not member:
            return False, "Selected user is not an active member of this care circle."

        caregiver_name = member["name"]

        # Reset all existing primary designations for this elderly profile
        conn.execute(
            "UPDATE care_circle SET is_primary = 0 WHERE elderly_user_id = ?",
            (elderly_user_id,),
        )

        # Designate new primary and ensure editor access
        conn.execute(
            """UPDATE care_circle
               SET is_primary = 1, permission_level = 'editor', connection_role = 'caregiver', updated_at = CURRENT_TIMESTAMP
               WHERE elderly_user_id = ? AND member_user_id = ?""",
            (elderly_user_id, caregiver_user_id),
        )

        # Notify designated caregiver
        conn.execute(
            """INSERT INTO notifications
               (user_id, elderly_user_id, alert_type, title, message)
               VALUES (?, ?, 'system', ?, ?)""",
            (
                caregiver_user_id,
                elderly_user_id,
                "Designated as Primary Caregiver",
                f"You have been designated as the primary caregiver for profile #{elderly_user_id}.",
            ),
        )

    log_activity(
        elderly_user_id,
        actor_user["id"],
        "Primary Caregiver Assigned",
        f"Designated {caregiver_name} as primary caregiver",
    )
    return True, f"{caregiver_name} is now designated as the primary caregiver."


# ==========================================
# CARE NOTES MODULE
# ==========================================

def add_care_note(
    elderly_user_id: int,
    author_user: dict,
    title: str,
    content: str,
    category: str = "general",
    visibility: str = "circle",
) -> tuple[bool, str, int | None]:
    """
    Creates a shared care note for an elderly profile.
    - Server-side authorization: only editor caregivers or elderly user can create notes.
    - Visibility: 'circle' (shared with family and caregivers) or 'caregivers_only' (hidden from family).
    - Non-prescriptive validation: rejected if empty or improper.
    """
    if not author_user:
        return False, "Authentication required.", None

    if not can_manage_care_circle(author_user, elderly_user_id):
        raise PermissionError(f"User #{author_user.get('id')} lacks permission to write care notes for profile #{elderly_user_id}")

    clean_title = title.strip()
    if len(clean_title) < 2:
        return False, "Note title must be at least 2 characters.", None

    clean_content = content.strip()
    if len(clean_content) < 4:
        return False, "Note content must be at least 4 characters.", None

    clean_visibility = visibility.strip().lower()
    if clean_visibility not in ("circle", "caregivers_only"):
        clean_visibility = "circle"

    clean_cat = category.strip().lower()
    if not clean_cat:
        clean_cat = "general"

    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO care_notes
               (elderly_user_id, author_id, title, content, category, visibility, is_archived, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (elderly_user_id, author_user["id"], clean_title, clean_content, clean_cat, clean_visibility),
        )
        note_id = cursor.lastrowid

    log_activity(
        elderly_user_id,
        author_user["id"],
        "Added Care Note",
        f"Added care note '{clean_title}' ({clean_cat})",
    )
    return True, "Care note saved successfully.", note_id


def get_care_notes(elderly_user_id: int, user: dict, include_archived: bool = False) -> list[dict]:
    """
    Returns care notes for an elderly profile with server-side authorization.
    Privacy enforcement:
    - Family members (viewers) see ONLY notes with visibility = 'circle'.
    - Notes marked 'caregivers_only' are strictly excluded from family view.
    """
    if not user:
        return []

    enforce_elderly_access(user, elderly_user_id, write_access=False)

    is_family_viewer = (user.get("role") == "family")

    with get_connection() as conn:
        # Check explicit permission level in circle if caregiver
        if not is_family_viewer and user["id"] != elderly_user_id:
            link = conn.execute(
                "SELECT permission_level, connection_role FROM care_circle WHERE elderly_user_id = ? AND member_user_id = ?",
                (elderly_user_id, user["id"]),
            ).fetchone()
            if link and (link["connection_role"] == "family" or link["permission_level"] == "viewer"):
                is_family_viewer = True

        query = """
            SELECT cn.id, cn.elderly_user_id, cn.author_id, cn.title, cn.content,
                   cn.category, cn.visibility, cn.is_archived, cn.created_at, cn.updated_at,
                   u_auth.name as author_name, u_auth.role as author_role
            FROM care_notes cn
            JOIN users u_auth ON cn.author_id = u_auth.id
            WHERE cn.elderly_user_id = ?
        """
        params = [elderly_user_id]

        if not include_archived:
            query += " AND cn.is_archived = 0"

        # Privacy filter: family members cannot see caregivers_only notes
        if is_family_viewer:
            query += " AND cn.visibility = 'circle'"

        query += " ORDER BY cn.created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def update_care_note(
    note_id: int,
    user: dict,
    title: str,
    content: str,
    category: str = "general",
    visibility: str = "circle",
) -> tuple[bool, str]:
    """Updates an existing care note."""
    if not user:
        return False, "Authentication required."

    clean_title = title.strip()
    clean_content = content.strip()
    if len(clean_title) < 2 or len(clean_content) < 4:
        return False, "Title and content must not be blank."

    clean_visibility = visibility.strip().lower()
    if clean_visibility not in ("circle", "caregivers_only"):
        clean_visibility = "circle"

    with get_connection() as conn:
        note = conn.execute(
            "SELECT id, elderly_user_id, author_id FROM care_notes WHERE id = ?",
            (note_id,),
        ).fetchone()
        if not note:
            return False, "Care note not found."

        elderly_id = note["elderly_user_id"]
        # Author or editor caregiver can edit
        if note["author_id"] != user["id"] and not can_manage_care_circle(user, elderly_id):
            raise PermissionError("Unauthorized to edit this care note.")

        conn.execute(
            """UPDATE care_notes
               SET title = ?, content = ?, category = ?, visibility = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (clean_title, clean_content, category.strip().lower(), clean_visibility, note_id),
        )

    log_activity(elderly_id, user["id"], "Updated Care Note", f"Updated care note '{clean_title}'")
    return True, "Care note updated successfully."


def archive_care_note(note_id: int, user: dict) -> tuple[bool, str]:
    """Soft archives a care note."""
    if not user:
        return False, "Authentication required."

    with get_connection() as conn:
        note = conn.execute(
            "SELECT id, elderly_user_id, author_id, title FROM care_notes WHERE id = ?",
            (note_id,),
        ).fetchone()
        if not note:
            return False, "Care note not found."

        elderly_id = note["elderly_user_id"]
        if note["author_id"] != user["id"] and not can_manage_care_circle(user, elderly_id):
            raise PermissionError("Unauthorized to archive this care note.")

        conn.execute("UPDATE care_notes SET is_archived = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (note_id,))

    log_activity(elderly_id, user["id"], "Archived Care Note", f"Archived care note '{note['title']}'")
    return True, "Care note archived."


def delete_care_note(note_id: int, user: dict) -> tuple[bool, str]:
    """Deletes a care note with authorization."""
    if not user:
        return False, "Authentication required."

    with get_connection() as conn:
        note = conn.execute(
            "SELECT id, elderly_user_id, author_id, title FROM care_notes WHERE id = ?",
            (note_id,),
        ).fetchone()
        if not note:
            return False, "Care note not found."

        elderly_id = note["elderly_user_id"]
        if note["author_id"] != user["id"] and not can_manage_care_circle(user, elderly_id):
            raise PermissionError("Unauthorized to delete this care note.")

        conn.execute("DELETE FROM care_notes WHERE id = ?", (note_id,))

    log_activity(elderly_id, user["id"], "Deleted Care Note", f"Deleted care note '{note['title']}'")
    return True, "Care note deleted."


def check_permission(elderly_user_id: int, user: dict, required_level: str = "viewer") -> bool:
    """Helper to verify care circle permission level."""
    if not user:
        return False
    if user["id"] == elderly_user_id:
        return True
    with get_connection() as conn:
        row = conn.execute(
            "SELECT permission_level, status FROM care_circle WHERE elderly_user_id = ? AND member_user_id = ? AND status = 'active'",
            (elderly_user_id, user["id"]),
        ).fetchone()
        if not row:
            return False
        if required_level == "viewer":
            return True
        return row["permission_level"] == "editor"


def add_care_circle_member(elderly_user_id: int, member_user_id: int, relationship: str = "Caregiver", permission_level: str = "editor", connection_role: str = "caregiver") -> bool:
    """Compatibility helper: directly adds or updates an active care circle member connection."""
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO care_circle
               (elderly_user_id, member_user_id, relationship, permission_level, connection_role, status)
               VALUES (?, ?, ?, ?, ?, 'active')""",
            (elderly_user_id, member_user_id, relationship, permission_level, connection_role),
        )
        return True
