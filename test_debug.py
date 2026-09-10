import re

KNOWN_COUNTRIES = {}
MONTH_NAMES_MAP = {}
UNIT_NORMALIZATION_MAP = {}
DATE_DD_MM_YYYY_REGEX = None
DATE_MM_YYYY_REGEX = None
DATE_MM_YY_REGEX = None
DATE_MONTHNAME_YYYY_REGEX = None
DATE_DD_MONTHNAME_YYYY_REGEX = None
RELATIVE_DATE_REGEX = None
PINCODE_REGEX = None
INSTRUCTION_STOP_WORDS = []
INSTRUCTION_REFERENCE_REGEX = None
NET_QTY_MULTIPACK_REGEX = None
ADDRESS_INDICATORS = []


def is_nutrition_context(text): return False
def has_address_indicator(text): return False

def normalize_mrp(raw_amount_str: str) -> dict:
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
        return {"amount": None, "currency": "INR", "_valid": False}
    return float(match.group(1))

print(normalize_mrp('Maximum Retail Price ₹1,299'))
print(normalize_mrp('MRP: ₹3,500.00 (inclusive of taxes)'))
