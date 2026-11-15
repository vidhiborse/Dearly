import csv
import io
import re
from datetime import date, datetime
import sqlite3
import plotly.graph_objects as go
from database import get_connection
from services.activity_service import log_activity
from services.permissions import enforce_elderly_access

SUPPORTED_MEASUREMENTS = [
    "Blood Pressure",
    "Blood Sugar",
    "Weight",
    "Heart Rate",
    "Oxygen Saturation (SpO2)",
    "Body Temperature",
]

OBSERVATION_CATEGORIES = [
    "general",
    "energy_sleep",
    "appetite_diet",
    "mobility",
    "mood_wellbeing",
    "post_visit",
]

# Standard reference range guidelines (strictly informational; not diagnostic)
REFERENCE_RANGES = {
    "Blood Pressure": {
        "systolic": (90, 120),
        "diastolic": (60, 80),
        "unit": "mmHg",
        "description": "Systolic 90-120 mmHg, Diastolic 60-80 mmHg",
    },
    "Blood Sugar": {
        "fasting": (70, 99),
        "before_meal": (70, 130),
        "after_meal": (70, 140),
        "random": (70, 140),
        "unit": "mg/dL",
        "description": "Fasting: 70-99 mg/dL; After meal: < 140 mg/dL",
    },
    "Heart Rate": {
        "range": (60, 100),
        "unit": "bpm",
        "description": "Resting Heart Rate: 60-100 bpm",
    },
    "Oxygen Saturation (SpO2)": {
        "range": (95, 100),
        "unit": "%",
        "description": "Resting SpO2: 95-100%",
    },
    "Body Temperature": {
        "celsius": (36.1, 37.2),
        "fahrenheit": (97.0, 99.0),
        "description": "Oral temperature: 36.1-37.2 °C (97.0-99.0 °F)",
    },
}


def evaluate_reference_range(
    reading_type: str,
    numeric_value: float = None,
    unit: str = "",
    systolic: int = None,
    diastolic: int = None,
    context: str = "",
) -> dict:
    """
    Evaluates whether a measurement falls within standard reference guidelines.
    Returns status ('within_range', 'outside_range', 'informational') and neutral disclaimer.
    Never confirms medical conditions or diagnoses.
    """
    clean_type = reading_type.strip()
    neutral_warning = (
        "This reading is outside the configured reference range. "
        "Consider discussing it with a qualified healthcare professional."
    )

    if "Blood Pressure" in clean_type:
        if systolic is not None and diastolic is not None:
            sys_norm = (systolic >= 90 and systolic <= 120)
            dia_norm = (diastolic >= 60 and diastolic <= 80)
            if sys_norm and dia_norm:
                return {
                    "status": "within_range",
                    "label": "Within standard reference range",
                    "warning": None,
                }
            return {
                "status": "outside_range",
                "label": "Outside standard reference range",
                "warning": neutral_warning,
            }

    elif "Blood Sugar" in clean_type:
        if numeric_value is not None:
            val_mgdl = numeric_value
            if unit.lower() == "mmol/l":
                val_mgdl = numeric_value * 18.0182

            ctx_clean = (context or "").lower()
            if "after" in ctx_clean:
                max_norm = 140.0
                min_norm = 70.0
            else:
                max_norm = 100.0
                min_norm = 70.0

            if min_norm <= val_mgdl <= max_norm:
                return {
                    "status": "within_range",
                    "label": "Within standard reference range",
                    "warning": None,
                }
            return {
                "status": "outside_range",
                "label": "Outside standard reference range",
                "warning": neutral_warning,
            }

    elif "Heart Rate" in clean_type:
        if numeric_value is not None:
            if 60 <= numeric_value <= 100:
                return {
                    "status": "within_range",
                    "label": "Within standard reference range",
                    "warning": None,
                }
            return {
                "status": "outside_range",
                "label": "Outside standard reference range",
                "warning": neutral_warning,
            }

    elif "Oxygen Saturation" in clean_type or "SpO2" in clean_type:
        if numeric_value is not None:
            if 95 <= numeric_value <= 100:
                return {
                    "status": "within_range",
                    "label": "Within standard reference range",
                    "warning": None,
                }
            return {
                "status": "outside_range",
                "label": "Outside standard reference range",
                "warning": neutral_warning,
            }

    elif "Temperature" in clean_type:
        if numeric_value is not None:
            u_clean = unit.upper()
            if "F" in u_clean:
                is_norm = 97.0 <= numeric_value <= 99.0
            else:
                is_norm = 36.1 <= numeric_value <= 37.2

            if is_norm:
                return {
                    "status": "within_range",
                    "label": "Within standard reference range",
                    "warning": None,
                }
            return {
                "status": "outside_range",
                "label": "Outside standard reference range",
                "warning": neutral_warning,
            }

    return {
        "status": "informational",
        "label": "Reference range informational",
        "warning": None,
    }


def extract_numeric_and_unit(text: str) -> tuple[float | None, str]:
    """Extracts numeric value and optional unit suffix from raw text string."""
    if not text:
        return None, ""
    text_clean = text.strip()
    match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*(.*)$", text_clean)
    if match:
        try:
            return float(match.group(1)), match.group(2).strip()
        except ValueError:
            return None, ""
    return None, ""


def validate_health_measurement(
    reading_type: str,
    reading_value: str = "",
    unit: str = "",
    systolic: int = None,
    diastolic: int = None,
    numeric_value: float = None,
    context: str = "",
) -> dict:
    """
    Validates health reading values, units, and ranges.
    Raises ValueError for invalid formats, non-numeric values, or physically impossible figures.
    Flags readings outside standard ranges with neutral clinical warnings.
    """
    if not reading_type or reading_type.strip() not in SUPPORTED_MEASUREMENTS and not any(
        s in reading_type for s in ["Blood Pressure", "Blood Sugar", "Weight", "Heart Rate", "SpO2", "Temperature"]
    ):
        raise ValueError(f"Unsupported measurement type: '{reading_type}'.")

    rtype = reading_type.strip()
    clean_unit = (unit or "").strip()
    clean_context = (context or "").strip()

    # 1. Blood Pressure Validation
    if "Blood Pressure" in rtype:
        if systolic is None or diastolic is None:
            # Parse from reading_value if not explicitly provided
            if not reading_value or "/" not in reading_value:
                raise ValueError("Blood Pressure must be formatted as 'Systolic/Diastolic' (e.g. 120/80).")
            bp_clean = reading_value.split()[0]
            parts = bp_clean.split("/")
            try:
                systolic = int(parts[0].strip())
                diastolic = int(parts[1].strip())
            except (ValueError, IndexError):
                raise ValueError("Blood Pressure values must be valid integers (e.g. 120/80).")

        if systolic <= 0 or diastolic <= 0:
            raise ValueError("Blood Pressure values must be positive numbers.")

        if systolic <= diastolic:
            raise ValueError("Systolic blood pressure must be higher than diastolic blood pressure.")

        # Boundaries
        if systolic < 40 or systolic > 300:
            raise ValueError(f"Systolic blood pressure of {systolic} mmHg is outside plausible physical boundaries (40-300 mmHg).")
        if diastolic < 25 or diastolic > 200:
            raise ValueError(f"Diastolic blood pressure of {diastolic} mmHg is outside plausible physical boundaries (25-200 mmHg).")

        if not clean_unit:
            clean_unit = "mmHg"
        elif clean_unit.lower() != "mmhg":
            raise ValueError(f"Invalid unit for Blood Pressure: '{clean_unit}'. Expected 'mmHg'.")

        formatted_val = f"{systolic}/{diastolic} {clean_unit}"
        eval_res = evaluate_reference_range(rtype, systolic=systolic, diastolic=diastolic)
        return {
            "reading_type": "Blood Pressure",
            "reading_value": formatted_val,
            "systolic": systolic,
            "diastolic": diastolic,
            "numeric_value": float(systolic),
            "unit": "mmHg",
            "context": clean_context,
            "warning": eval_res.get("warning"),
            "status": eval_res.get("status"),
        }

    # 2. Blood Sugar Validation
    elif "Blood Sugar" in rtype:
        if numeric_value is None:
            if not reading_value:
                raise ValueError("Blood Sugar reading value is required.")
            parsed_num, parsed_unit = extract_numeric_and_unit(reading_value)
            if parsed_num is None:
                raise ValueError("Blood Sugar reading must be a valid numeric value.")
            numeric_value = parsed_num
            if not clean_unit and parsed_unit:
                clean_unit = parsed_unit

        if numeric_value <= 0:
            raise ValueError("Blood Sugar reading must be greater than zero.")

        valid_units = ["mg/dL", "mmol/L"]
        if not clean_unit:
            if "mmol" in reading_value.lower():
                clean_unit = "mmol/L"
            else:
                clean_unit = "mg/dL"

        matched_unit = next((u for u in valid_units if u.lower() == clean_unit.lower()), None)
        if not matched_unit:
            raise ValueError(f"Invalid unit for Blood Sugar: '{clean_unit}'. Supported: mg/dL, mmol/L.")
        clean_unit = matched_unit

        # Bounds check
        if clean_unit == "mg/dL" and (numeric_value < 20 or numeric_value > 1000):
            raise ValueError(f"Blood sugar of {numeric_value} mg/dL is outside plausible limits (20-1000 mg/dL).")
        elif clean_unit == "mmol/L" and (numeric_value < 1.1 or numeric_value > 55.5):
            raise ValueError(f"Blood sugar of {numeric_value} mmol/L is outside plausible limits (1.1-55.5 mmol/L).")

        formatted_val = f"{numeric_value:g} {clean_unit}"
        eval_res = evaluate_reference_range(rtype, numeric_value=numeric_value, unit=clean_unit, context=clean_context)
        return {
            "reading_type": "Blood Sugar",
            "reading_value": formatted_val,
            "systolic": None,
            "diastolic": None,
            "numeric_value": numeric_value,
            "unit": clean_unit,
            "context": clean_context or "fasting",
            "warning": eval_res.get("warning"),
            "status": eval_res.get("status"),
        }

    # 3. Weight Validation
    elif "Weight" in rtype:
        if numeric_value is None:
            if not reading_value:
                raise ValueError("Weight measurement is required.")
            parsed_num, parsed_unit = extract_numeric_and_unit(reading_value)
            if parsed_num is None:
                raise ValueError("Weight must be a valid numeric value.")
            numeric_value = parsed_num
            if not clean_unit and parsed_unit:
                clean_unit = parsed_unit

        if numeric_value <= 0:
            raise ValueError("Weight measurement must be greater than zero.")

        valid_units = ["kg", "lb"]
        if not clean_unit:
            clean_unit = "lb" if "lb" in reading_value.lower() else "kg"

        matched_unit = next((u for u in valid_units if u.lower() == clean_unit.lower()), None)
        if not matched_unit:
            raise ValueError(f"Invalid unit for Weight: '{clean_unit}'. Supported: kg, lb.")
        clean_unit = matched_unit

        if clean_unit == "kg" and (numeric_value < 10 or numeric_value > 500):
            raise ValueError(f"Weight of {numeric_value} kg is outside plausible physical boundaries (10-500 kg).")
        elif clean_unit == "lb" and (numeric_value < 22 or numeric_value > 1100):
            raise ValueError(f"Weight of {numeric_value} lb is outside plausible physical boundaries (22-1100 lb).")

        formatted_val = f"{numeric_value:.1f} {clean_unit}"
        return {
            "reading_type": "Weight",
            "reading_value": formatted_val,
            "systolic": None,
            "diastolic": None,
            "numeric_value": numeric_value,
            "unit": clean_unit,
            "context": clean_context,
            "warning": None,
            "status": "informational",
        }

    # 4. Heart Rate Validation
    elif "Heart Rate" in rtype:
        if numeric_value is None:
            if not reading_value:
                raise ValueError("Heart Rate measurement is required.")
            parsed_num, parsed_unit = extract_numeric_and_unit(reading_value)
            if parsed_num is None:
                raise ValueError("Heart Rate must be a valid numeric integer.")
            numeric_value = parsed_num
            if not clean_unit and parsed_unit:
                clean_unit = parsed_unit

        if numeric_value <= 0:
            raise ValueError("Heart Rate must be greater than zero.")

        if numeric_value < 30 or numeric_value > 250:
            raise ValueError(f"Heart Rate of {numeric_value} bpm is outside plausible physical limits (30-250 bpm).")

        if not clean_unit:
            clean_unit = "bpm"
        elif clean_unit.lower() != "bpm":
            raise ValueError(f"Invalid unit for Heart Rate: '{clean_unit}'. Expected 'bpm'.")

        formatted_val = f"{int(numeric_value)} {clean_unit}"
        eval_res = evaluate_reference_range(rtype, numeric_value=numeric_value, unit="bpm")
        return {
            "reading_type": "Heart Rate",
            "reading_value": formatted_val,
            "systolic": None,
            "diastolic": None,
            "numeric_value": numeric_value,
            "unit": "bpm",
            "context": clean_context,
            "warning": eval_res.get("warning"),
            "status": eval_res.get("status"),
        }

    # 5. Oxygen Saturation (SpO2) Validation
    elif "Oxygen Saturation" in rtype or "SpO2" in rtype:
        if numeric_value is None:
            if not reading_value:
                raise ValueError("Oxygen Saturation reading is required.")
            parsed_num, parsed_unit = extract_numeric_and_unit(reading_value)
            if parsed_num is None:
                raise ValueError("Oxygen Saturation must be a valid numeric percentage.")
            numeric_value = parsed_num
            if not clean_unit and parsed_unit:
                clean_unit = parsed_unit

        if numeric_value < 50 or numeric_value > 100:
            raise ValueError(f"Oxygen Saturation (SpO2) of {numeric_value}% is invalid. Expected between 50% and 100%.")

        if not clean_unit:
            clean_unit = "%"
        elif clean_unit != "%":
            raise ValueError(f"Invalid unit for SpO2: '{clean_unit}'. Expected '%'.")

        formatted_val = f"{numeric_value:g} %"
        eval_res = evaluate_reference_range(rtype, numeric_value=numeric_value, unit="%")
        return {
            "reading_type": "Oxygen Saturation (SpO2)",
            "reading_value": formatted_val,
            "systolic": None,
            "diastolic": None,
            "numeric_value": numeric_value,
            "unit": "%",
            "context": clean_context,
            "warning": eval_res.get("warning"),
            "status": eval_res.get("status"),
        }

    # 6. Body Temperature Validation
    elif "Temperature" in rtype:
        if numeric_value is None:
            if not reading_value:
                raise ValueError("Body Temperature reading is required.")
            parsed_num, parsed_unit = extract_numeric_and_unit(reading_value)
            if parsed_num is None:
                raise ValueError("Body Temperature must be a valid number.")
            numeric_value = parsed_num
            if not clean_unit and parsed_unit:
                clean_unit = parsed_unit

        if not clean_unit:
            clean_unit = "°F" if "f" in reading_value.lower() else "°C"

        valid_temp_units = ["°C", "°F", "C", "F"]
        matched_unit = next((u for u in valid_temp_units if u.upper() == clean_unit.upper()), None)
        if not matched_unit:
            raise ValueError(f"Invalid unit for Temperature: '{clean_unit}'. Expected '°C' or '°F'.")

        is_c = "C" in matched_unit.upper()
        norm_unit = "°C" if is_c else "°F"

        if is_c and (numeric_value < 30.0 or numeric_value > 45.0):
            raise ValueError(f"Temperature of {numeric_value} °C is outside plausible human boundaries (30.0-45.0 °C).")
        elif not is_c and (numeric_value < 86.0 or numeric_value > 113.0):
            raise ValueError(f"Temperature of {numeric_value} °F is outside plausible human boundaries (86.0-113.0 °F).")

        formatted_val = f"{numeric_value:.1f} {norm_unit}"
        eval_res = evaluate_reference_range(rtype, numeric_value=numeric_value, unit=norm_unit)
        return {
            "reading_type": "Body Temperature",
            "reading_value": formatted_val,
            "systolic": None,
            "diastolic": None,
            "numeric_value": numeric_value,
            "unit": norm_unit,
            "context": clean_context,
            "warning": eval_res.get("warning"),
            "status": eval_res.get("status"),
        }

    raise ValueError(f"Unrecognized measurement type: '{reading_type}'.")


def add_health_reading(
    elderly_user_id: int,
    reading_type: str,
    reading_value: str = "",
    recorded_on: str = None,
    notes: str = "",
    recorded_by: int = None,
    unit: str = None,
    systolic: int = None,
    diastolic: int = None,
    numeric_value: float = None,
    context: str = "",
    recorded_time: str = None,
    appointment_id: int = None,
    user: dict = None,
) -> int:
    """
    Records a validated health measurement with server-side authorization and activity logging.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    val_res = validate_health_measurement(
        reading_type=reading_type,
        reading_value=reading_value,
        unit=unit,
        systolic=systolic,
        diastolic=diastolic,
        numeric_value=numeric_value,
        context=context,
    )

    rec_date = (recorded_on or date.today().isoformat()).strip()
    rec_time = (recorded_time or datetime.now().strftime("%I:%M %p")).strip()
    clean_notes = (notes or "").strip()
    clean_context = val_res.get("context", "")

    actor_id = recorded_by or (user.get("id") if user else elderly_user_id)

    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO health_readings
               (elderly_user_id, reading_type, reading_value, systolic, diastolic, numeric_value,
                unit, context, recorded_on, recorded_time, recorded_by, appointment_id, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                elderly_user_id,
                val_res["reading_type"],
                val_res["reading_value"],
                val_res["systolic"],
                val_res["diastolic"],
                val_res["numeric_value"],
                val_res["unit"],
                clean_context,
                rec_date,
                rec_time,
                actor_id,
                appointment_id,
                clean_notes,
            ),
        )
        reading_id = cursor.lastrowid

    log_activity(
        elderly_user_id,
        actor_id,
        "Logged Health Reading",
        f"Recorded {val_res['reading_type']}: {val_res['reading_value']} on {rec_date} ({rec_time}). {clean_notes}".strip(),
    )
    return reading_id


# Alias for flexible naming
add_health_measurement = add_health_reading



def get_health_readings(
    elderly_user_id: int,
    reading_type: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 50,
    appointment_id: int = None,
    user: dict = None,
) -> list[dict]:
    """
    Retrieves chronological health readings with actor attribution and audit flags.
    Enforces server-side read permissions.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    query = """
        SELECT r.id, r.elderly_user_id, r.reading_type, r.reading_value,
               r.systolic, r.diastolic, r.numeric_value, r.unit, r.context,
               r.recorded_on, r.recorded_time, r.recorded_by, r.appointment_id,
               r.notes, r.is_corrected, r.corrected_at, r.corrected_by, r.correction_notes,
               r.created_at, r.updated_at,
               u_rec.name as recorded_by_name,
               u_corr.name as corrected_by_name
        FROM health_readings r
        LEFT JOIN users u_rec ON r.recorded_by = u_rec.id
        LEFT JOIN users u_corr ON r.corrected_by = u_corr.id
        WHERE r.elderly_user_id = ?
    """
    params = [elderly_user_id]

    if reading_type and reading_type.lower() != "all":
        query += " AND (r.reading_type = ? OR r.reading_type LIKE ?)"
        params.extend([reading_type, f"%{reading_type}%"])

    if start_date:
        query += " AND r.recorded_on >= ?"
        params.append(start_date)

    if end_date:
        query += " AND r.recorded_on <= ?"
        params.append(end_date)

    if appointment_id:
        query += " AND r.appointment_id = ?"
        params.append(appointment_id)

    query += " ORDER BY r.recorded_on DESC, r.id DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        readings = [dict(r) for r in rows]

    for item in readings:
        eval_res = evaluate_reference_range(
            reading_type=item["reading_type"],
            numeric_value=item["numeric_value"],
            unit=item["unit"] or "",
            systolic=item["systolic"],
            diastolic=item["diastolic"],
            context=item["context"] or "",
        )
        item["status_label"] = eval_res["label"]
        item["is_outside_range"] = (eval_res["status"] == "outside_range")
        item["range_warning"] = eval_res["warning"]

    return readings


def get_health_reading_by_id(reading_id: int, user: dict = None) -> dict | None:
    """Retrieves a single health reading with access verification."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT r.*, u_rec.name as recorded_by_name, u_corr.name as corrected_by_name
               FROM health_readings r
               LEFT JOIN users u_rec ON r.recorded_by = u_rec.id
               LEFT JOIN users u_corr ON r.corrected_by = u_corr.id
               WHERE r.id = ?""",
            (reading_id,),
        ).fetchone()
        if not row:
            return None
        reading = dict(row)

    if user:
        enforce_elderly_access(user, reading["elderly_user_id"], write_access=False)

    return reading


def correct_health_reading(
    reading_id: int,
    elderly_user_id: int,
    new_value: str,
    reason: str,
    changed_by: int = None,
    new_notes: str = None,
    systolic: int = None,
    diastolic: int = None,
    unit: str = None,
    user: dict = None,
) -> bool:
    """
    Corrects an incorrect health reading while strictly preserving the audit history in health_record_audit.
    Enforces write permissions.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    if not reason or len(reason.strip()) < 3:
        raise ValueError("A clear reason for record correction is required (minimum 3 characters).")

    old_record = get_health_reading_by_id(reading_id)
    if not old_record or old_record["elderly_user_id"] != elderly_user_id:
        raise ValueError(f"Health reading #{reading_id} not found for this elderly profile.")

    actor_id = changed_by or (user.get("id") if user else elderly_user_id)

    # Validate new measurement
    val_res = validate_health_measurement(
        reading_type=old_record["reading_type"],
        reading_value=new_value,
        unit=unit or old_record.get("unit"),
        systolic=systolic,
        diastolic=diastolic,
        context=old_record.get("context", ""),
    )

    clean_notes = (new_notes if new_notes is not None else old_record.get("notes", "")).strip()

    with get_connection() as conn:
        # 1. Insert previous state into audit table
        conn.execute(
            """INSERT INTO health_record_audit
               (reading_id, elderly_user_id, changed_by, old_reading_type, old_reading_value,
                old_unit, new_reading_type, new_reading_value, new_unit, reason_for_change, changed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                reading_id,
                elderly_user_id,
                actor_id,
                old_record["reading_type"],
                old_record["reading_value"],
                old_record.get("unit", ""),
                val_res["reading_type"],
                val_res["reading_value"],
                val_res["unit"],
                reason.strip(),
            ),
        )

        # 2. Update health_readings record
        conn.execute(
            """UPDATE health_readings
               SET reading_value = ?,
                   systolic = ?,
                   diastolic = ?,
                   numeric_value = ?,
                   unit = ?,
                   notes = ?,
                   is_corrected = 1,
                   corrected_at = CURRENT_TIMESTAMP,
                   corrected_by = ?,
                   correction_notes = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND elderly_user_id = ?""",
            (
                val_res["reading_value"],
                val_res["systolic"],
                val_res["diastolic"],
                val_res["numeric_value"],
                val_res["unit"],
                clean_notes,
                actor_id,
                reason.strip(),
                reading_id,
                elderly_user_id,
            ),
        )

    log_activity(
        elderly_user_id,
        actor_id,
        "Corrected Health Reading",
        f"Corrected reading #{reading_id} ({old_record['reading_type']}) from '{old_record['reading_value']}' to '{val_res['reading_value']}'. Reason: {reason.strip()}",
    )
    return True


def get_health_record_audit(
    reading_id: int = None,
    elderly_user_id: int = None,
    user: dict = None,
) -> list[dict]:
    """Retrieves immutable audit history for health record corrections."""
    if user and elderly_user_id:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    query = """
        SELECT a.id, a.reading_id, a.elderly_user_id, a.changed_by,
               a.old_reading_type, a.old_reading_value, a.old_unit,
               a.new_reading_type, a.new_reading_value, a.new_unit,
               a.reason_for_change, a.changed_at,
               u.name as changed_by_name
        FROM health_record_audit a
        LEFT JOIN users u ON a.changed_by = u.id
        WHERE 1=1
    """
    params = []
    if reading_id:
        query += " AND a.reading_id = ?"
        params.append(reading_id)
    if elderly_user_id:
        query += " AND a.elderly_user_id = ?"
        params.append(elderly_user_id)

    query += " ORDER BY a.changed_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def add_health_observation(
    elderly_user_id: int,
    observation_text: str,
    recorded_by: int = None,
    category: str = "general",
    recorded_on: str = None,
    recorded_time: str = None,
    appointment_id: int = None,
    user: dict = None,
) -> int:
    """
    Records a qualitative wellbeing observation (e.g., fatigue, sleep quality, appetite).
    Observations are strictly non-diagnostic notes.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    if not observation_text or len(observation_text.strip()) < 3:
        raise ValueError("Observation note is required (minimum 3 characters).")

    clean_cat = category.strip().lower() if category else "general"
    if clean_cat not in OBSERVATION_CATEGORIES:
        clean_cat = "general"

    rec_date = (recorded_on or date.today().isoformat()).strip()
    rec_time = (recorded_time or datetime.now().strftime("%I:%M %p")).strip()
    actor_id = recorded_by or (user.get("id") if user else elderly_user_id)

    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO health_observations
               (elderly_user_id, observation_text, category, recorded_on, recorded_time, appointment_id, recorded_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (elderly_user_id, observation_text.strip(), clean_cat, rec_date, rec_time, appointment_id, actor_id),
        )
        obs_id = cursor.lastrowid

    log_activity(
        elderly_user_id,
        actor_id,
        "Logged Health Observation",
        f"Recorded [{clean_cat}] observation: {observation_text.strip()}",
    )
    return obs_id


def get_health_observations(
    elderly_user_id: int,
    category: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 30,
    appointment_id: int = None,
    user: dict = None,
) -> list[dict]:
    """Retrieves chronological health observations."""
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    query = """
        SELECT o.id, o.elderly_user_id, o.observation_text, o.category,
               o.recorded_on, o.recorded_time, o.appointment_id, o.recorded_by,
               o.created_at, o.updated_at,
               u.name as recorded_by_name,
               a.doctor_name as appointment_doctor,
               a.appointment_date as appointment_date
        FROM health_observations o
        LEFT JOIN users u ON o.recorded_by = u.id
        LEFT JOIN appointments a ON o.appointment_id = a.id
        WHERE o.elderly_user_id = ?
    """
    params = [elderly_user_id]

    if category and category.lower() != "all":
        query += " AND o.category = ?"
        params.append(category.lower())

    if start_date:
        query += " AND o.recorded_on >= ?"
        params.append(start_date)

    if end_date:
        query += " AND o.recorded_on <= ?"
        params.append(end_date)

    if appointment_id:
        query += " AND o.appointment_id = ?"
        params.append(appointment_id)

    query += " ORDER BY o.recorded_on DESC, o.recorded_time DESC, o.id DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_latest_vitals(elderly_user_id: int, user: dict = None) -> dict:
    """
    Returns latest readings for standard vital signs with reference status.
    Preserves backward compatibility for summary service and existing views.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    types = [
        "Blood Pressure",
        "Blood Sugar (Fasting)",
        "Blood Sugar",
        "Weight",
        "Heart Rate",
        "Oxygen Saturation (SpO2)",
        "Body Temperature",
    ]

    latest = {}
    with get_connection() as conn:
        for t in types:
            row = conn.execute(
                """SELECT id, reading_type, reading_value, systolic, diastolic,
                          numeric_value, unit, context, recorded_on, recorded_time, notes, is_corrected
                   FROM health_readings
                   WHERE elderly_user_id = ? AND (reading_type = ? OR reading_type LIKE ?)
                   ORDER BY recorded_on DESC, id DESC
                   LIMIT 1""",
                (elderly_user_id, t, f"%{t}%"),
            ).fetchone()

            if row:
                d = dict(row)
                eval_res = evaluate_reference_range(
                    reading_type=d["reading_type"],
                    numeric_value=d["numeric_value"],
                    unit=d["unit"] or "",
                    systolic=d["systolic"],
                    diastolic=d["diastolic"],
                    context=d["context"] or "",
                )
                d["status_label"] = eval_res["label"]
                d["is_outside_range"] = (eval_res["status"] == "outside_range")
                d["warning"] = eval_res["warning"]
                latest[t] = d
            else:
                latest[t] = None

    # Harmonize Blood Sugar aliases
    if not latest.get("Blood Sugar (Fasting)") and latest.get("Blood Sugar"):
        latest["Blood Sugar (Fasting)"] = latest["Blood Sugar"]
    elif not latest.get("Blood Sugar") and latest.get("Blood Sugar (Fasting)"):
        latest["Blood Sugar"] = latest["Blood Sugar (Fasting)"]

    return latest


def get_health_summary(
    elderly_user_id: int,
    start_date: str = None,
    end_date: str = None,
    user: dict = None,
) -> dict:
    """
    Generates a structured health summary including latest measurements,
    record counts, reference range status, and recent observations.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    latest = get_latest_vitals(elderly_user_id, user=user)
    recent_obs = get_health_observations(elderly_user_id, limit=5, user=user)

    with get_connection() as conn:
        q_count = "SELECT COUNT(*) as count FROM health_readings WHERE elderly_user_id = ?"
        p_count = [elderly_user_id]
        if start_date:
            q_count += " AND recorded_on >= ?"
            p_count.append(start_date)
        if end_date:
            q_count += " AND recorded_on <= ?"
            p_count.append(end_date)
        total_readings = conn.execute(q_count, p_count).fetchone()["count"]

        first_last = conn.execute(
            """SELECT MIN(recorded_on) as first_date, MAX(recorded_on) as last_date
               FROM health_readings WHERE elderly_user_id = ?""",
            (elderly_user_id,),
        ).fetchone()

    return {
        "latest_vitals": latest,
        "recent_observations": recent_obs,
        "total_readings_in_period": total_readings,
        "first_recorded_date": first_last["first_date"] if first_last else None,
        "last_recorded_date": first_last["last_date"] if first_last else None,
    }


def sanitize_csv_cell(val) -> str:
    """
    Sanitizes values against CSV Formula Injection (OWASP CWE-1236).
    Prepends a single quote if string begins with =, +, -, @, tab, or carriage return.
    """
    if val is None:
        return ""
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


def export_health_records_csv(
    elderly_user_id: int,
    reading_type: str = None,
    start_date: str = None,
    end_date: str = None,
    user: dict = None,
) -> str:
    """
    Exports filtered health readings for an authorized elderly profile in standard CSV format.
    Sanitizes cell data against CSV formula injection (OWASP CWE-1236).
    Ensures safe, permission-checked data extraction.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    readings = get_health_readings(
        elderly_user_id=elderly_user_id,
        reading_type=reading_type,
        start_date=start_date,
        end_date=end_date,
        limit=1000,
        user=user,
    )

    with get_connection() as conn:
        elderly_row = conn.execute("SELECT name FROM users WHERE id = ?", (elderly_user_id,)).fetchone()
        elderly_name = elderly_row["name"] if elderly_row else f"Patient #{elderly_user_id}"

    output = io.StringIO()
    writer = csv.writer(output)

    def write_safe_row(cells):
        writer.writerow([sanitize_csv_cell(c) for c in cells])

    # Header
    write_safe_row([
        "Record ID",
        "Patient Name",
        "Date",
        "Time",
        "Measurement Type",
        "Reading Value",
        "Unit",
        "Context",
        "Recorded By",
        "Status / Range",
        "Notes",
        "Corrected",
        "Correction Reason",
    ])

    for r in readings:
        write_safe_row([
            r["id"],
            elderly_name,
            r["recorded_on"],
            r.get("recorded_time") or "",
            r["reading_type"],
            r["reading_value"],
            r.get("unit") or "",
            r.get("context") or "",
            r.get("recorded_by_name") or f"User #{r.get('recorded_by')}",
            r.get("status_label") or "",
            r.get("notes") or "",
            "Yes" if r.get("is_corrected") else "No",
            r.get("correction_notes") or "",
        ])

    return output.getvalue()


def create_health_chart(readings: list[dict], measurement_type: str) -> go.Figure | None:
    """
    Builds accessible Plotly trend charts for health measurements.
    Strictly follows DESIGN.md styling and displays informative empty states for insufficient data.
    """
    if not readings:
        return None

    # Filter readings for the exact type
    m_clean = measurement_type.strip().lower()
    matching = [r for r in readings if m_clean in r["reading_type"].lower()]
    if not matching:
        return None

    # Sort chronologically ascending for the x-axis
    sorted_data = sorted(
        matching,
        key=lambda x: (x["recorded_on"], x.get("recorded_time") or ""),
    )

    dates = [f"{r['recorded_on']} {r.get('recorded_time') or ''}".strip() for r in sorted_data]

    # 1. Blood Pressure Trend (Systolic & Diastolic)
    if "pressure" in m_clean:
        systolic_vals = []
        diastolic_vals = []
        valid_dates = []
        for r, dt in zip(sorted_data, dates):
            sys_val = r.get("systolic")
            dia_val = r.get("diastolic")
            if sys_val is None and "/" in r["reading_value"]:
                parts = r["reading_value"].split()[0].split("/")
                try:
                    sys_val = int(parts[0])
                    dia_val = int(parts[1])
                except (ValueError, IndexError):
                    continue
            if sys_val and dia_val:
                systolic_vals.append(sys_val)
                diastolic_vals.append(dia_val)
                valid_dates.append(dt)

        if not valid_dates:
            return None

        fig = go.Figure()
        # Systolic Line
        fig.add_trace(go.Scatter(
            x=valid_dates,
            y=systolic_vals,
            mode="lines+markers",
            name="Systolic (mmHg)",
            line=dict(color="#234B70", width=3),
            marker=dict(size=8, color="#234B70"),
        ))
        # Diastolic Line
        fig.add_trace(go.Scatter(
            x=valid_dates,
            y=diastolic_vals,
            mode="lines+markers",
            name="Diastolic (mmHg)",
            line=dict(color="#23815C", width=3),
            marker=dict(size=8, color="#23815C"),
        ))
        # Normal reference bands
        fig.add_hrect(y0=90, y1=120, fillcolor="#234B70", opacity=0.06, line_width=0, annotation_text="Systolic Reference (90-120)", annotation_position="top left")
        fig.add_hrect(y0=60, y1=80, fillcolor="#23815C", opacity=0.06, line_width=0, annotation_text="Diastolic Reference (60-80)", annotation_position="bottom left")

        fig.update_layout(
            title="Blood Pressure Trend (mmHg)",
            height=340,
            margin=dict(l=30, r=30, t=40, b=30),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            font=dict(family="Plus Jakarta Sans, sans-serif", size=13, color="#243447"),
            yaxis=dict(title="mmHg", gridcolor="#EDF2F7", tickfont=dict(color="#243447")),
            xaxis=dict(title="Measurement Date & Time", gridcolor="#EDF2F7", tickfont=dict(color="#243447")),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        return fig

    # 2. Blood Sugar Trend
    elif "sugar" in m_clean:
        y_vals = []
        valid_dates = []
        unit_label = "mg/dL"
        for r, dt in zip(sorted_data, dates):
            nv = r.get("numeric_value")
            if nv is None:
                num_s = "".join(c for c in r["reading_value"].split()[0] if c.isdigit() or c == ".")
                try:
                    nv = float(num_s)
                except ValueError:
                    continue
            if nv:
                y_vals.append(nv)
                valid_dates.append(dt)
                if r.get("unit"):
                    unit_label = r["unit"]

        if not valid_dates:
            return None

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=valid_dates,
            y=y_vals,
            mode="lines+markers",
            name=f"Blood Sugar ({unit_label})",
            line=dict(color="#234B70", width=3),
            marker=dict(size=8, color="#234B70"),
        ))
        if unit_label.lower() == "mg/dl":
            fig.add_hrect(y0=70, y1=140, fillcolor="#23815C", opacity=0.08, line_width=0, annotation_text="Target Range (70-140 mg/dL)", annotation_position="top left")

        fig.update_layout(
            title=f"Blood Sugar Trend ({unit_label})",
            height=320,
            margin=dict(l=30, r=30, t=40, b=30),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            font=dict(family="Plus Jakarta Sans, sans-serif", size=13, color="#243447"),
            yaxis=dict(title=unit_label, gridcolor="#EDF2F7", tickfont=dict(color="#243447")),
            xaxis=dict(title="Measurement Date & Time", gridcolor="#EDF2F7", tickfont=dict(color="#243447")),
        )
        return fig

    # 3. Weight Trend
    elif "weight" in m_clean:
        y_vals = []
        valid_dates = []
        unit_label = "kg"
        for r, dt in zip(sorted_data, dates):
            nv = r.get("numeric_value")
            if nv is None:
                num_s = "".join(c for c in r["reading_value"].split()[0] if c.isdigit() or c == ".")
                try:
                    nv = float(num_s)
                except ValueError:
                    continue
            if nv:
                y_vals.append(nv)
                valid_dates.append(dt)
                if r.get("unit"):
                    unit_label = r["unit"]

        if not valid_dates:
            return None

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=valid_dates,
            y=y_vals,
            mode="lines+markers",
            name=f"Weight ({unit_label})",
            line=dict(color="#234B70", width=3),
            marker=dict(size=8, color="#234B70"),
        ))
        fig.update_layout(
            title=f"Weight Trend ({unit_label})",
            height=320,
            margin=dict(l=30, r=30, t=40, b=30),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            font=dict(family="Plus Jakarta Sans, sans-serif", size=13, color="#243447"),
            yaxis=dict(title=unit_label, gridcolor="#EDF2F7", tickfont=dict(color="#243447")),
            xaxis=dict(title="Measurement Date & Time", gridcolor="#EDF2F7", tickfont=dict(color="#243447")),
        )
        return fig

    # 4. Heart Rate Trend
    elif "heart" in m_clean:
        y_vals = []
        valid_dates = []
        for r, dt in zip(sorted_data, dates):
            nv = r.get("numeric_value")
            if nv is None:
                num_s = "".join(c for c in r["reading_value"].split()[0] if c.isdigit())
                try:
                    nv = float(num_s)
                except ValueError:
                    continue
            if nv:
                y_vals.append(nv)
                valid_dates.append(dt)

        if not valid_dates:
            return None

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=valid_dates,
            y=y_vals,
            mode="lines+markers",
            name="Heart Rate (bpm)",
            line=dict(color="#234B70", width=3),
            marker=dict(size=8, color="#234B70"),
        ))
        fig.add_hrect(y0=60, y1=100, fillcolor="#23815C", opacity=0.08, line_width=0, annotation_text="Standard Resting Range (60-100 bpm)", annotation_position="top left")

        fig.update_layout(
            title="Heart Rate Trend (bpm)",
            height=320,
            margin=dict(l=30, r=30, t=40, b=30),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            font=dict(family="Plus Jakarta Sans, sans-serif", size=13, color="#243447"),
            yaxis=dict(title="bpm", gridcolor="#EDF2F7", tickfont=dict(color="#243447")),
            xaxis=dict(title="Measurement Date & Time", gridcolor="#EDF2F7", tickfont=dict(color="#243447")),
        )
        return fig

    # 5. SpO2 Trend
    elif "spo2" in m_clean or "oxygen" in m_clean:
        y_vals = []
        valid_dates = []
        for r, dt in zip(sorted_data, dates):
            nv = r.get("numeric_value")
            if nv is None:
                num_s = "".join(c for c in r["reading_value"].split()[0] if c.isdigit() or c == ".")
                try:
                    nv = float(num_s)
                except ValueError:
                    continue
            if nv:
                y_vals.append(nv)
                valid_dates.append(dt)

        if not valid_dates:
            return None

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=valid_dates,
            y=y_vals,
            mode="lines+markers",
            name="SpO2 (%)",
            line=dict(color="#234B70", width=3),
            marker=dict(size=8, color="#234B70"),
        ))
        fig.add_hrect(y0=95, y1=100, fillcolor="#23815C", opacity=0.08, line_width=0, annotation_text="Normal Resting Range (95-100%)", annotation_position="top left")

        fig.update_layout(
            title="Oxygen Saturation (SpO2 %)",
            height=320,
            margin=dict(l=30, r=30, t=40, b=30),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            font=dict(family="Plus Jakarta Sans, sans-serif", size=13, color="#243447"),
            yaxis=dict(title="SpO2 %", gridcolor="#EDF2F7", tickfont=dict(color="#243447")),
            xaxis=dict(title="Measurement Date & Time", gridcolor="#EDF2F7", tickfont=dict(color="#243447")),
        )
        return fig

    return None
