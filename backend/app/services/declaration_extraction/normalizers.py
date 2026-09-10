"""Normalizers for LegalMetrix AI Declaration Extraction.

Ensures deterministic, safe structured conversions while preserving all raw text and units.

Hardened v1.5.0:
- normalize_organization_address: detect and split long single-line blobs that contain
  an address indicator or PIN code so the name is not the entire blob.
- normalize_phone: stricter valid-digit range check (7–13 digits, not including country prefix).
- normalize_batch_number: also reject all-uppercase-word tokens that match instruction stop words
  even without the INSTRUCTION_REFERENCE pattern.
- normalize_net_quantity: support count-only units (tablets, capsules, sachets, etc.).
- normalize_mrp: tighten upper-bound sanity to 99999 (5-digit MRP cap for real products).
"""
import re
from typing import Any, Dict, List, Optional, Tuple
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
    ADDRESS_INDICATORS,
    has_address_indicator,
    is_nutrition_context,
)

# ---------------------------------------------------------------------------
# MRP
# ---------------------------------------------------------------------------

def normalize_mrp(raw_amount_str: str, has_taxes_incl: Optional[bool] = None) -> Dict[str, Any]:
    """Normalize MRP extracted string into structured monetary value.

    Sanity bounds: amount must be > 0 and ≤ 99999 (a ₹1,00,000 product is beyond normal
    retail; if seen it is almost certainly an OCR artefact like a barcode or FSSAI number).
    """
    clean_str = raw_amount_str.strip()
    if "," in clean_str:
        if "." in clean_str:
            clean_str = clean_str.replace(",", "")
        else:
            m = re.search(r",(\d{2})(?:\D|$)", clean_str)
            if m and len(re.findall(r",", clean_str)) == 1:
                clean_str = clean_str.replace(",", ".")
            else:
                clean_str = clean_str.replace(",", "")

    match = re.search(r"([0-9]+(?:\.[0-9]{1,2})?)", clean_str)
    if not match:
        return {
            "amount": None,
            "currency": "INR",
            "taxes_inclusive": has_taxes_incl,
            "raw_amount": raw_amount_str,
            "_valid": False,
        }

    try:
        amount = float(match.group(1))
        if amount <= 0 or amount > 99999:
            return {
                "amount": None,
                "currency": "INR",
                "taxes_inclusive": has_taxes_incl,
                "raw_amount": raw_amount_str,
                "_valid": False,
            }

        return {
            "amount": round(amount, 2),
            "currency": "INR",
            "taxes_inclusive": has_taxes_incl if has_taxes_incl is not None else True,
            "raw_amount": raw_amount_str.strip(),
            "_valid": True,
        }
    except ValueError:
        return {
            "amount": None,
            "currency": "INR",
            "taxes_inclusive": has_taxes_incl,
            "raw_amount": raw_amount_str,
            "_valid": False,
        }


# ---------------------------------------------------------------------------
# Net Quantity
# ---------------------------------------------------------------------------

# Count-only unit set (lowercase canonical after UNIT_NORMALIZATION_MAP lookup)
_COUNT_ONLY_UNITS = {
    "tablets", "capsules", "sachets", "strips", "vials", "ampoules",
    "pouches", "bottles", "jars", "rolls", "sheets", "pairs", "bags",
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
    Supports count-only units (tablets, capsules, sachets, etc.).
    """
    clean_val_str = raw_value_str.strip().replace(",", ".")

    # 1. Multi-pack compound expressions
    mp_match = NET_QTY_MULTIPACK_REGEX.search(clean_val_str)
    if mp_match:
        units_count = int(mp_match.group(1))
        unit_weight = float(mp_match.group(2))
        raw_u1 = mp_match.group(3) or "g"
        norm_u1 = UNIT_NORMALIZATION_MAP.get(raw_u1.lower(), raw_u1.lower())

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
            "value": int(total_val) if float(total_val).is_integer() else total_val,
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
            "_valid": True,
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

    # 3. Canonical SI base representation
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
        elif norm_unit in ("pcs", "units"):
            canonical_val = val
            canonical_unit = "units"
        elif norm_unit in _COUNT_ONLY_UNITS:
            # Count-only: canonical = as-is
            canonical_val = val
            canonical_unit = norm_unit

    is_valid = val is not None and val > 0
    res = {
        "value": int(val) if val is not None and float(val).is_integer() else val,
        "unit": norm_unit,
        "raw_unit": raw_unit.strip() if raw_unit else None,
        "canonical_value": canonical_val,
        "canonical_unit": canonical_unit,
        "_valid": is_valid,
    }
    if multipack_info:
        res["is_multipack"] = True
        res["multipack"] = multipack_info
    return res


# ---------------------------------------------------------------------------
# Date
# ---------------------------------------------------------------------------

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
            "_valid": True,
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
                "_valid": True,
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
                "_valid": True,
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
                "_valid": True,
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
                "_valid": True,
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
                "_valid": True,
            }

    return {
        "date": None,
        "raw": clean_text,
        "semantic_type": semantic_label,
        "_valid": False,
    }


# ---------------------------------------------------------------------------
# Country
# ---------------------------------------------------------------------------

def normalize_country(raw_country_str: str) -> Dict[str, Any]:
    """Normalize country text conservatively without guessing."""
    clean = raw_country_str.strip().strip(".:-")
    # Truncate trailing junk words (address text bleeding in from the capture group)
    clean = re.split(r"\s{2,}|\n|\r", clean)[0].strip()
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
        "_valid": bool(norm_country or (len(clean_upper) >= 2)),
    }


# ---------------------------------------------------------------------------
# Phone
# ---------------------------------------------------------------------------

def normalize_phone(raw_phone_str: str) -> Dict[str, Any]:
    """
    Normalize phone number: preserve raw, normalize spaces and dashes.
    Rejects licence numbers (such as 14-digit FSSAI licence) or invalid numbers.
    Valid Indian phone numbers: 7–13 significant digits (excl. country prefix +91).
    """
    clean = raw_phone_str.strip().strip(".:-")
    digits_only = re.sub(r"[^\d]", "", clean)

    # Reject 14-digit FSSAI licences or non-phone identifiers
    if len(digits_only) == 14:
        return {
            "number": None,
            "digits": digits_only,
            "raw": raw_phone_str.strip(),
            "is_valid": False,
            "rejection_reason": "14-digit FSSAI licence number",
        }

    # Strip leading country code 91 if present and not a toll-free
    sig_digits = digits_only
    if sig_digits.startswith("91") and len(sig_digits) == 12 and not sig_digits.startswith("1800"):
        sig_digits = sig_digits[2:]

    # Reject if digit count is outside reasonable phone range (7–10 for Indian numbers)
    toll_free_valid = digits_only.startswith("1800") and 10 <= len(digits_only) <= 11
    mobile_valid = len(sig_digits) == 10 and sig_digits[0] in "6789"
    landline_valid = len(sig_digits) in (7, 8, 11) or (
        len(digits_only) in range(8, 12) and digits_only.startswith("0")
    )

    if not (toll_free_valid or mobile_valid or landline_valid):
        return {
            "number": None,
            "digits": digits_only,
            "raw": raw_phone_str.strip(),
            "is_valid": False,
            "rejection_reason": f"digit count {len(digits_only)} is outside valid phone range",
        }

    # Format toll-free numbers cleanly
    if digits_only.startswith("1800"):
        if len(digits_only) == 10:
            formatted = f"1800-{digits_only[4:7]}-{digits_only[7:]}"
        elif len(digits_only) == 11:
            formatted = f"1800-{digits_only[4:8]}-{digits_only[8:]}"
        else:
            formatted = clean
    elif len(sig_digits) == 10:
        formatted = f"+91 {sig_digits[:5]} {sig_digits[5:]}"
    else:
        formatted = re.sub(r"\s+", " ", clean)

    return {
        "number": formatted,
        "digits": digits_only,
        "raw": raw_phone_str.strip(),
        "is_valid": True,
    }


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def normalize_email(raw_email_str: str) -> Dict[str, Any]:
    """
    Normalize email: remove OCR whitespace around @ and dots, lowercase.
    """
    clean = raw_email_str.strip().strip(".:-")
    clean = re.sub(r"\s*\[at\]\s*", "@", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*@\s*", "@", clean)
    clean = re.sub(r"\s*\.\s*", ".", clean)
    clean = clean.lower()

    is_valid = bool(re.match(r"^[a-z0-9_.+-]+@[a-z0-9-]+\.[a-z0-9-.]+$", clean))
    return {
        "email": clean,
        "raw": raw_email_str.strip(),
        "_valid": is_valid,
    }


# ---------------------------------------------------------------------------
# Organization / Address
# ---------------------------------------------------------------------------

def normalize_organization_address(raw_text: str, role: str) -> Dict[str, Any]:
    """
    Extract organization name, address, and PIN code from multi-line text block.

    Hardening: if the raw text is a single long line but contains address indicators
    (city names, state names, PLOT, DIST, etc.) or a PIN code, attempt to split the
    name at the first address indicator token so the name is not the entire blob.
    """
    clean = raw_text.strip().strip(".:-")
    lines = [ln.strip() for ln in re.split(r"\n|\r\n|\r", clean) if ln.strip()]

    if len(lines) >= 2:
        name = lines[0]
        address = ", ".join(lines[1:])
    else:
        # Single line — check if it embeds address info
        single = lines[0] if lines else clean
        split_name, split_addr = _split_name_from_address(single)
        if split_name is not None:
            name = split_name
            address = split_addr if split_addr else ""
        else:
            name = single
            address = ""

    # Clean up name: strip trailing commas/dash
    name = name.strip(" ,-")

    pin_match = PINCODE_REGEX.search(clean)
    pincode = pin_match.group(1).replace(" ", "") if pin_match else None

    # Validity: name must be ≥2 chars and not be a pure number
    name_valid = bool(name) and len(re.findall(r"[a-zA-Z]", name)) >= 2

    return {
        "name": name,
        "address": address,
        "pincode": pincode,
        "role": role,
        "raw": clean,
        "_valid": name_valid,
    }


def _split_name_from_address(single_line: str) -> Tuple[str, Optional[str]]:
    """
    Attempt to split a single-line org+address blob into (name, address).
    """
    COMPANY_SUFFIXES = {"LTD", "LTD.", "LIMITED", "PVT", "PVT.", "PRIVATE", "LLP", "INC", "INC.", "CORP", "CORP.", "CO.", "COMPANY"}

    # Strategy 1: Look for a comma right after a company suffix
    tokens = single_line.split()
    for i, tok in enumerate(tokens):
        cleaned_tok = tok.rstrip(",.-").upper()
        if cleaned_tok in COMPANY_SUFFIXES:
            # Check if there is a comma immediately following this token in the raw string or if it's the end of a clause
            # We can reconstruct the name up to this token.
            name_part = " ".join(tokens[:i+1])
            # If the name_part actually ended with a comma in the original string...
            if tok.endswith(",") or (i + 1 < len(tokens) and tokens[i+1].startswith(",")):
                name_clean = name_part.rstrip(",- ")
                addr_clean = " ".join(tokens[i+1:]).lstrip(",- ")
                return name_clean, addr_clean
            
            # If no comma, we still might be at the boundary of a name, but we need to verify the next token isn't just another name part
            if i + 1 < len(tokens):
                next_tok_upper = tokens[i+1].rstrip(",.-").upper()
                if next_tok_upper in {ind.upper() for ind in ADDRESS_INDICATORS} or next_tok_upper.isdigit() or "/" in tokens[i+1]:
                    name_clean = name_part.rstrip(",- ")
                    addr_clean = " ".join(tokens[i+1:]).lstrip(",- ")
                    return name_clean, addr_clean

    # Strategy 2: First address indicator token
    for i, tok in enumerate(tokens):
        tok_upper = tok.strip(".,:-").upper()
        if tok_upper in {ind.upper() for ind in ADDRESS_INDICATORS} or (i > 0 and "/" in tok and any(c.isdigit() for c in tok)):
            # Walk backwards from i to find a comma
            sub_str = " ".join(tokens[:i])
            if "," in sub_str:
                last_comma_idx = sub_str.rindex(",")
                name_part = sub_str[:last_comma_idx].strip()
                addr_part = single_line[len(name_part):].lstrip(" ,.-")
                return name_part.strip(), addr_part.strip()
            
            if i > 0:
                name_part = " ".join(tokens[:i]).strip(" ,.-")
                addr_part = " ".join(tokens[i:]).strip()
                return name_part, addr_part

    # Strategy 3: Split before PIN code
    pin_match = PINCODE_REGEX.search(single_line)
    if pin_match:
        before_pin = single_line[: pin_match.start()].rstrip(" ,.-")
        last_sep = max(before_pin.rfind(","), before_pin.rfind(" - "))
        if last_sep > 0:
            name_part = single_line[:last_sep].strip()
            addr_part = single_line[last_sep + 1:].strip(" ,")
            if name_part:
                return name_part, addr_part

    return single_line, None



# ---------------------------------------------------------------------------
# Batch / Lot Number
# ---------------------------------------------------------------------------

def normalize_batch_number(raw_batch_str: str) -> Dict[str, Any]:
    """
    Normalize batch / lot number string.
    Distinguishes genuine alphanumeric batch identifiers from instructions (e.g. 'printed on the pack').

    Hardening:
    - Also reject tokens that are purely instruction stop words even without the full regex.
    - Require at least one digit character for batch codes (pure alphabetic strings like
      "PLAIN" are almost always product name spillover, not batch numbers).
    """
    clean = raw_batch_str.strip().strip(".:- #")

    if not clean:
        return {"batch_number": None, "raw": raw_batch_str.strip()}

    # If the text is an instruction or references packing location
    if INSTRUCTION_REFERENCE_REGEX.search(clean):
        return {
            "batch_number": None,
            "raw": raw_batch_str.strip(),
            "is_instruction_only": True,
        }

    words = [w.strip(".:-,/").upper() for w in clean.split() if w.strip(".:-,/")]
    if not words:
        return {"batch_number": None, "raw": raw_batch_str.strip()}

    if words[0] in INSTRUCTION_STOP_WORDS and len(words) <= 5:
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
        return {"batch_number": None, "raw": raw_batch_str.strip()}

    # Must contain at least 1 digit (pure letter strings are almost never batch numbers)
    digit_count = len(re.findall(r"\d", clean))
    if digit_count < 1:
        return {
            "batch_number": None,
            "raw": raw_batch_str.strip(),
            "rejection_reason": "no digits found; likely product name spillover",
        }

    # Reject if excessively long (> 25 chars) and contains spaces — likely a sentence
    if len(clean) > 25 and " " in clean:
        return {
            "batch_number": None,
            "raw": raw_batch_str.strip(),
            "rejection_reason": "value too long and contains spaces; likely sentence spillover",
        }

    return {
        "batch_number": clean,
        "raw": raw_batch_str.strip(),
        "_valid": True,
    }


# ---------------------------------------------------------------------------
# Commodity Name
# ---------------------------------------------------------------------------

def normalize_commodity_name(raw_name_str: str) -> Dict[str, Any]:
    """
    Normalize commodity / product name string.
    Rejects isolated symbols, punctuation ('(', '-'), instruction words, or nutrition text.
    """
    first_line = raw_name_str.strip().split("\n")[0].split("\r")[0]
    clean = first_line.strip().strip(".:- #()[]{}\"'")

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

    # Reject specific exclusive prefixes
    EXCLUDED_PREFIXES = ("SKU", "FSN", "MODEL", "BARCODE", "COLOR", "PHONE", "EMAIL", "MRP", "BATCH", "LICENCE", "LOT NO", "B. NO", "L. NO", "PKD", "MFD")
    upper_clean = clean.upper()
    for prefix in EXCLUDED_PREFIXES:
        if upper_clean.startswith(prefix):
            return {
                "commodity_name": None,
                "raw": raw_name_str.strip(),
                "is_valid": False,
                "rejection_reason": f"starts with excluded prefix: {prefix}"
            }

    # Reject excessively long single-token values (> 60 chars likely OCR merged)
    if len(clean) > 60:
        return {
            "commodity_name": None,
            "raw": raw_name_str.strip(),
            "is_valid": False,
            "rejection_reason": "value too long; likely OCR merge artefact",
        }

    return {
        "commodity_name": clean.title(),
        "raw": raw_name_str.strip(),
        "is_valid": True,
        "_valid": True,
    }
