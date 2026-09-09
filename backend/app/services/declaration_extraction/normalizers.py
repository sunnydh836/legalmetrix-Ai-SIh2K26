"""Normalizers for LegalMetrix AI Declaration Extraction.

Ensures deterministic, safe structured conversions while preserving all raw text and units.
"""
import re
from typing import Any, Dict, Optional, Tuple
from app.services.declaration_extraction.patterns import (
    KNOWN_COUNTRIES,
    MONTH_NAMES_MAP,
    UNIT_NORMALIZATION_MAP,
    DATE_DD_MM_YYYY_REGEX,
    DATE_MM_YYYY_REGEX,
    DATE_MM_YY_REGEX,
    DATE_MONTHNAME_YYYY_REGEX,
    DATE_DD_MONTHNAME_YYYY_REGEX,
    RELATIVE_DATE_REGEX,
    PINCODE_REGEX,
    INSTRUCTION_STOP_WORDS,
    INSTRUCTION_REFERENCE_REGEX,
    NET_QTY_MULTIPACK_REGEX,
    is_nutrition_context,
)


def normalize_mrp(raw_amount_str: str, has_taxes_incl: Optional[bool] = None) -> Dict[str, Any]:
    """Normalize MRP extracted string into structured monetary value."""
    clean_str = raw_amount_str.strip().replace(",", ".")
    # Extract floating point number
    match = re.search(r"([0-9]+(?:\.[0-9]{1,2})?)", clean_str)
    if not match:
        return {
            "amount": None,
            "currency": "INR",
            "taxes_inclusive": has_taxes_incl,
            "raw_amount": raw_amount_str,
        }

    try:
        amount = float(match.group(1))
        if amount <= 0 or amount > 1000000:
            return {
                "amount": None,
                "currency": "INR",
                "taxes_inclusive": has_taxes_incl,
                "raw_amount": raw_amount_str,
            }

        return {
            "amount": round(amount, 2),
            "currency": "INR",
            "taxes_inclusive": has_taxes_incl if has_taxes_incl is not None else True,
            "raw_amount": raw_amount_str.strip(),
        }
    except ValueError:
        return {
            "amount": None,
            "currency": "INR",
            "taxes_inclusive": has_taxes_incl,
            "raw_amount": raw_amount_str,
        }


def normalize_net_quantity(
    raw_value_str: str,
    raw_unit: Optional[str] = None,
    multipack_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Normalize Net Quantity into structured numerical value and standardized unit.
    Preserves original unit and converts to canonical SI standard without overwriting printed unit.
    Supports multi-pack compound expressions (e.g., '10 N x 82.7 g = 827 g').
    """
    # 1. Check if raw_value_str itself is a multi-pack compound expression
    clean_val_str = raw_value_str.strip().replace(",", ".")
    mp_match = NET_QTY_MULTIPACK_REGEX.search(clean_val_str)
    if mp_match:
        units_count = int(mp_match.group(1))
        unit_weight = float(mp_match.group(2))
        raw_u1 = mp_match.group(3) or "g"
        norm_u1 = UNIT_NORMALIZATION_MAP.get(raw_u1.lower(), raw_u1.lower())

        # Total parsed or calculated
        if mp_match.group(4):
            total_val = float(mp_match.group(4))
            raw_u2 = mp_match.group(5) or raw_u1
            norm_u2 = UNIT_NORMALIZATION_MAP.get(raw_u2.lower(), norm_u1)
        else:
            total_val = round(units_count * unit_weight, 4)
            norm_u2 = norm_u1

        canonical_val = total_val
        canonical_unit = norm_u2
        if norm_u2 == "kg":
            canonical_val = round(total_val * 1000, 4)
            canonical_unit = "g"
        elif norm_u2 == "L":
            canonical_val = round(total_val * 1000, 4)
            canonical_unit = "ml"

        return {
            "value": int(total_val) if total_val.is_integer() else total_val,
            "unit": norm_u2,
            "raw_unit": raw_u2 if mp_match.group(4) else raw_u1,
            "canonical_value": canonical_val,
            "canonical_unit": canonical_unit,
            "is_multipack": True,
            "multipack": {
                "units": units_count,
                "unit_value": unit_weight,
                "unit_unit": norm_u1,
                "raw_expression": raw_value_str.strip(),
            },
        }

    # 2. Standard single-quantity normalization
    try:
        val = float(clean_val_str)
    except ValueError:
        val = None

    if raw_unit:
        clean_unit = raw_unit.strip().lower()
        norm_unit = UNIT_NORMALIZATION_MAP.get(clean_unit, clean_unit)
    else:
        clean_unit = None
        norm_unit = None

    # Compute canonical SI base representation (e.g. g or ml)
    canonical_val = None
    canonical_unit = None
    if val is not None and norm_unit:
        if norm_unit == "kg":
            canonical_val = round(val * 1000, 4)
            canonical_unit = "g"
        elif norm_unit == "mg":
            canonical_val = round(val / 1000, 6)
            canonical_unit = "g"
        elif norm_unit == "g":
            canonical_val = val
            canonical_unit = "g"
        elif norm_unit == "L":
            canonical_val = round(val * 1000, 4)
            canonical_unit = "ml"
        elif norm_unit == "ml":
            canonical_val = val
            canonical_unit = "ml"
        elif norm_unit in ["pcs", "units"]:
            canonical_val = val
            canonical_unit = "units"

    res = {
        "value": int(val) if val is not None and val.is_integer() else val,
        "unit": norm_unit,
        "raw_unit": raw_unit.strip() if raw_unit else None,
        "canonical_value": canonical_val,
        "canonical_unit": canonical_unit,
    }
    if multipack_info:
        res["is_multipack"] = True
        res["multipack"] = multipack_info
    return res


def normalize_date(date_text: str, semantic_label: str) -> Dict[str, Any]:
    """
    Normalize date text into structured date representation.
    Supports DD/MM/YYYY, MM/YYYY, MM/YY, Month YYYY, and relative declarations (e.g. '9 Months from Mfg').
    """
    clean_text = date_text.strip()

    # Check relative expressions first
    rel_match = RELATIVE_DATE_REGEX.search(clean_text)
    if rel_match:
        duration_num = int(rel_match.group(1))
        duration_unit = rel_match.group(2).upper()
        return {
            "date": None,
            "is_relative": True,
            "relative_duration": duration_num,
            "relative_unit": duration_unit,
            "relative_text": clean_text,
            "semantic_type": semantic_label,
        }

    # DD/MM/YYYY
    match_dd_mm_yyyy = DATE_DD_MM_YYYY_REGEX.search(clean_text)
    if match_dd_mm_yyyy:
        day = int(match_dd_mm_yyyy.group(1))
        month = int(match_dd_mm_yyyy.group(2))
        year = int(match_dd_mm_yyyy.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return {
                "date": f"{year:04d}-{month:02d}-{day:02d}",
                "day": day,
                "month": month,
                "year": year,
                "format": "DD/MM/YYYY",
                "semantic_type": semantic_label,
            }

    # DD Monthname YYYY (e.g. 15 AUG 2026)
    match_dd_month = DATE_DD_MONTHNAME_YYYY_REGEX.search(clean_text)
    if match_dd_month:
        day = int(match_dd_month.group(1))
        m_str = match_dd_month.group(2).upper()
        month = MONTH_NAMES_MAP.get(m_str)
        y_str = match_dd_month.group(3)
        year = int(y_str) if len(y_str) == 4 else int("20" + y_str)
        if month and 1 <= day <= 31:
            return {
                "date": f"{year:04d}-{month:02d}-{day:02d}",
                "day": day,
                "month": month,
                "year": year,
                "format": "DD-MMM-YYYY",
                "semantic_type": semantic_label,
            }

    # Monthname YYYY (e.g. AUG 2026, AUGUST 2026)
    match_month = DATE_MONTHNAME_YYYY_REGEX.search(clean_text)
    if match_month:
        m_str = match_month.group(1).upper()
        month = MONTH_NAMES_MAP.get(m_str)
        y_str = match_month.group(2)
        year = int(y_str) if len(y_str) == 4 else int("20" + y_str)
        if month:
            return {
                "date": f"{year:04d}-{month:02d}",
                "day": None,
                "month": month,
                "year": year,
                "format": "MMM YYYY",
                "semantic_type": semantic_label,
            }

    # MM/YYYY
    match_mm_yyyy = DATE_MM_YYYY_REGEX.search(clean_text)
    if match_mm_yyyy:
        month = int(match_mm_yyyy.group(1))
        year = int(match_mm_yyyy.group(2))
        if 1 <= month <= 12:
            return {
                "date": f"{year:04d}-{month:02d}",
                "day": None,
                "month": month,
                "year": year,
                "format": "MM/YYYY",
                "semantic_type": semantic_label,
            }

    # MM/YY
    match_mm_yy = DATE_MM_YY_REGEX.search(clean_text)
    if match_mm_yy:
        month = int(match_mm_yy.group(1))
        year = int("20" + match_mm_yy.group(2))
        if 1 <= month <= 12:
            return {
                "date": f"{year:04d}-{month:02d}",
                "day": None,
                "month": month,
                "year": year,
                "format": "MM/YY",
                "semantic_type": semantic_label,
            }

    return {
        "date": None,
        "raw": clean_text,
        "semantic_type": semantic_label,
    }


def normalize_country(raw_country_str: str) -> Dict[str, Any]:
    """Normalize country text conservatively without guessing."""
    clean = raw_country_str.strip().strip(".:-")
    clean_upper = re.sub(r"[^a-zA-Z\s]", "", clean).strip().upper()

    norm_country = KNOWN_COUNTRIES.get(clean_upper)
    if not norm_country:
        for k, v in KNOWN_COUNTRIES.items():
            if k in clean_upper:
                norm_country = v
                break

    return {
        "country": norm_country or clean.title(),
        "raw": clean,
        "is_recognized": bool(norm_country),
    }


def normalize_phone(raw_phone_str: str) -> Dict[str, Any]:
    """
    Normalize phone number: preserve raw, normalize spaces and dashes.
    Rejects licence numbers (such as 14-digit FSSAI licence) or invalid numbers.
    """
    clean = raw_phone_str.strip().strip(".:-")
    digits_only = re.sub(r"[^\d]", "", clean)

    # Reject 14-digit FSSAI licences or non-phone identifiers
    if len(digits_only) == 14 or (len(digits_only) > 10 and digits_only.startswith("100")):
        return {
            "number": None,
            "digits": digits_only,
            "raw": raw_phone_str.strip(),
            "is_valid": False,
        }

    # Format toll free numbers cleanly
    if digits_only.startswith("1800"):
        if len(digits_only) == 10:
            formatted = f"1800-{digits_only[4:7]}-{digits_only[7:]}"
        elif len(digits_only) == 11:
            formatted = f"1800-{digits_only[4:7]}-{digits_only[7:]}"
        else:
            formatted = clean
    elif len(digits_only) == 10:
        formatted = f"+91 {digits_only[:5]} {digits_only[5:]}"
    else:
        formatted = re.sub(r"\s+", " ", clean)

    return {
        "number": formatted,
        "digits": digits_only,
        "raw": raw_phone_str.strip(),
        "is_valid": True,
    }


def normalize_email(raw_email_str: str) -> Dict[str, Any]:
    """
    Normalize email: remove OCR whitespace around @ and dots, lowercase.
    """
    clean = raw_email_str.strip().strip(".:-")
    clean = re.sub(r"\s*\[at\]\s*", "@", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*@\s*", "@", clean)
    clean = re.sub(r"\s*\.\s*", ".", clean)
    clean = clean.lower()

    return {
        "email": clean,
        "raw": raw_email_str.strip(),
    }


def normalize_organization_address(raw_text: str, role: str) -> Dict[str, Any]:
    """
    Extract organization name, address, and PIN code from multi-line text block.
    """
    clean = raw_text.strip().strip(".:-")
    lines = [l.strip() for l in clean.split("\n") if l.strip()]

    name = lines[0] if lines else clean
    address = ", ".join(lines[1:]) if len(lines) > 1 else clean

    pin_match = PINCODE_REGEX.search(clean)
    pincode = pin_match.group(1).replace(" ", "") if pin_match else None

    return {
        "name": name,
        "address": address,
        "pincode": pincode,
        "role": role,
        "raw": clean,
    }


def normalize_batch_number(raw_batch_str: str) -> Dict[str, Any]:
    """
    Normalize batch / lot number string.
    Distinguishes genuine alphanumeric batch identifiers from instructions (e.g. 'printed on the pack').
    """
    clean = raw_batch_str.strip().strip(".:- #")

    # If the text is an instruction or references packing location
    if INSTRUCTION_REFERENCE_REGEX.search(clean):
        return {
            "batch_number": None,
            "raw": raw_batch_str.strip(),
            "is_instruction_only": True,
        }

    # Split into words and check if first token or entire value is instruction stop word
    words = [w.strip(".:-,/").upper() for w in clean.split() if w.strip(".:-,/")]
    if not words:
        return {
            "batch_number": None,
            "raw": raw_batch_str.strip(),
        }

    if words[0] in INSTRUCTION_STOP_WORDS and len(words) <= 5:
        # Check if there's any subsequent alphanumeric token that looks like a real batch code
        candidate_code = None
        for w in words[1:]:
            if w not in INSTRUCTION_STOP_WORDS and re.search(r"\d", w) and len(w) >= 2:
                candidate_code = w
                break
        if not candidate_code:
            return {
                "batch_number": None,
                "raw": raw_batch_str.strip(),
                "is_instruction_only": True,
            }
        clean = candidate_code

    # Must contain at least 2 alphanumeric characters
    alnum_count = len(re.findall(r"[a-zA-Z0-9]", clean))
    if alnum_count < 2:
        return {
            "batch_number": None,
            "raw": raw_batch_str.strip(),
        }

    return {
        "batch_number": clean,
        "raw": raw_batch_str.strip(),
    }


def normalize_commodity_name(raw_name_str: str) -> Dict[str, Any]:
    """
    Normalize commodity / product name string.
    Rejects isolated symbols, punctuation ('(', '-'), instruction words, or nutrition text.
    """
    first_line = raw_name_str.strip().split("\n")[0].split("\r")[0]
    clean = first_line.strip().strip(".:- #()[]{}")

    # Minimum validity: at least 3 alphabetic characters
    alpha_chars = re.findall(r"[a-zA-Z]", clean)
    if len(alpha_chars) < 3:
        return {
            "commodity_name": None,
            "raw": raw_name_str.strip(),
            "is_valid": False,
        }

    # Reject if it's nutrition context or instructions
    if is_nutrition_context(clean) or INSTRUCTION_REFERENCE_REGEX.search(clean):
        return {
            "commodity_name": None,
            "raw": raw_name_str.strip(),
            "is_valid": False,
        }

    return {
        "commodity_name": clean.title(),
        "raw": raw_name_str.strip(),
        "is_valid": True,
    }
