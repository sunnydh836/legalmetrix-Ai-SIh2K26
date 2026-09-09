"""Deterministic regexes, aliases, and keyword lexicons for Day 5 Declaration Extraction."""
import re
from typing import Dict, List, Pattern, Set

# -------------------------------------------------------------------
# Negative Context Lexicons (Nutrition, Instructions, Non-Phone Identifiers)
# -------------------------------------------------------------------

NUTRITION_HEADER_REGEX = re.compile(
    r"\b(?:NUTRITION(?:AL)?\s*(?:INFORMATION|FACTS?|PANEL|DECLARATION|VALUES?)|"
    r"PER\s+SERVE|PER\s+100\s*G|APPROX(?:IMATELY)?\s*PER\s+100\s*G|NUTRITIVE\s+VALUES?)\b",
    re.IGNORECASE,
)

NUTRITION_KEYWORD_REGEX = re.compile(
    r"\b(?:SERVING\s+SIZE|SERVINGS?\s+PER\s+CONTAINER|PER\s+SERVE|PER\s+100\s*G|PER\s+100G|"
    r"APPROX\.\s*\d+\s*(?:BISCUITS?|PIECES?|SERVES?)|"
    r"ENERGY|PROTEIN|CARBOHYDRATE|CARBS|SUGARS?|ADDED\s+SUGARS?|TOTAL\s+SUGARS?|TOTAL\s+FAT|"
    r"FATTY\s+ACIDS?|SATURATED\s+FAT(?:TY)?|TRANS\s+FAT(?:TY\s+ACIDS?)?|CHOLESTEROL|SODIUM|SALT|"
    r"RDA|RECOMMENDED\s+DIETARY\s+ALLOWANCE|RECOMMENDED\s+DIETARY|"
    r"DIETARY\s+FIB(?:ER|RE)|MINERALS?|VITAMINS?|CALCIUM|IRON|POTASSIUM)\b",
    re.IGNORECASE,
)

INSTRUCTION_REFERENCE_REGEX = re.compile(
    r"\b(?:PRINTED\s+(?:ON|BELOW|ABOVE|ON\s+THE\s+PACK)|"
    r"SEE\s+(?:PACK|CRIMP|BELOW|SIDE|TOP|BOTTOM|EMBOSSING|PANEL)|"
    r"REFER\s+TO\s+(?:PACK|CRIMP|BELOW|SIDE|TOP|BOTTOM|PANEL)|"
    r"REFER\s+(?:PACK|CRIMP|BELOW|SIDE|TOP|BOTTOM|PANEL)|"
    r"ON\s+THE\s+PACKAGING|ON\s+THE\s+PACK|FOR\s+(?:BATCH|PKD|MFD|EXP|USE\s+BEFORE)\s+SEE|"
    r"STAMPED\s+ON|EMBOSSED\s+ON|REFER\s+CRIMP)\b",
    re.IGNORECASE,
)

INSTRUCTION_STOP_WORDS: Set[str] = {
    "PRINTED", "PACK", "CRIMP", "BELOW", "ABOVE", "REFER", "SEE",
    "SIDE", "TOP", "BOTTOM", "EMBOSSING", "PACKAGING", "DATE",
    "DETAILS", "OF", "THE", "ON", "FOR", "AT", "PANEL", "NO", "NUMBER",
    "CODE", "LOT", "BATCH", "PRINTEDONTHEPACK", "PRINTEDONPACK",
}

LICENCE_OR_ID_REGEX = re.compile(
    r"\b(?:FSSAI|LIC\.?\s*(?:NO\.?|NUMBER)?|LICENCE|LICENSE|CIN|GSTIN|REG\.?\s*(?:NO\.?|NUMBER)?|BARCODE|EAN)\b",
    re.IGNORECASE,
)

FSSAI_NUMBER_PATTERN = re.compile(r"\b(?:100[0-9]{11}|[0-9]{14})\b")


def is_nutrition_context(text: str) -> bool:
    """Check if the text represents a nutrition table or nutrient declaration."""
    if not text:
        return False
    return bool(NUTRITION_HEADER_REGEX.search(text) or NUTRITION_KEYWORD_REGEX.search(text))


def is_instruction_only(text: str) -> bool:
    """Check if text is purely an instruction/reference without an actual value."""
    if not text:
        return False
    return bool(INSTRUCTION_REFERENCE_REGEX.search(text))


# -------------------------------------------------------------------
# MRP Patterns
# -------------------------------------------------------------------
MRP_PREFIX_KEYWORDS = [
    "MAXIMUM RETAIL PRICE",
    "MAX. RETAIL PRICE",
    "MAX RETAIL PRICE",
    "RETAIL PRICE",
    "RETAIL SALE PRICE",
    "M.R.P.",
    "M.R.P",
    "MRP",
    "MR P",
    "MRPE",
]

CURRENCY_SYMBOLS = [
    "₹",
    "RS.",
    "RS",
    "INR",
    "INR.",
    "RUPEES",
    "RUPEE",
]

# Strict MRP regex with word boundaries around currency tokens
MRP_EXPLICIT_REGEX = re.compile(
    r"\b(?:MAXIMUM\s+RETAIL\s+PRICE|MAX\.?\s+RETAIL\s+PRICE|RETAIL\s+(?:SALE\s+)?PRICE|M\.?R\.?P\.?[E]?)\b\s*[:\.\-]?\s*"
    r"(?:(?:₹|\bRS\.?|\bINR)\s*)?"
    r"([0-9]+(?:[\.,][0-9]{1,2})?)"
    r"(?:\s*(?:\/-|\/|INCL|INCLUSIVE))?",
    re.IGNORECASE,
)

MRP_AMOUNT_ONLY_REGEX = re.compile(
    r"(?:(?:₹|\bRS\.?|\bINR)\s*)([0-9]+(?:[\.,][0-9]{1,2})?)(?:\s*(?:\/-|\/))?",
    re.IGNORECASE,
)

INCL_TAXES_REGEX = re.compile(
    r"(?:INCL\.?|INCLUSIVE)\s+(?:OF\s+)?ALL\s+TAXES|TAXES\s+INCL\.?",
    re.IGNORECASE,
)

UNIT_SALE_PRICE_REGEX = re.compile(
    r"\b(?:UNIT\s+SALE\s+PRICE|USP)\s*[:\.\-]?\s*(?:(?:₹|\bRS\.?|\bINR)\s*)?([0-9]+(?:[\.,][0-9]{1,2})?)\s*(?:PER|\/)\s*([a-zA-Z]+)",
    re.IGNORECASE,
)

# -------------------------------------------------------------------
# Net Quantity Patterns
# -------------------------------------------------------------------
NET_QTY_PREFIX_KEYWORDS = [
    "NET QUANTITY",
    "NET QUANTITY:",
    "NET QTY",
    "NET QTY:",
    "NET WEIGHT",
    "NET WEIGHT:",
    "NET WT.",
    "NET WT",
    "NET WT:",
    "NET VOLUME",
    "NET VOL.",
    "NET VOL",
    "NET CONTENTS",
    "NET CONTENT",
    "NETWEIGHT",
    "NETWT",
    "NETQTY",
    "NETVOL",
    "N.W.",
    "N.W",
    "N.V.",
    "N.V",
]

# Standard unit aliases mapping
UNIT_NORMALIZATION_MAP = {
    "gm": "g",
    "gms": "g",
    "gram": "g",
    "grams": "g",
    "g": "g",
    "kg": "kg",
    "kgs": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "mg": "mg",
    "milligram": "mg",
    "milligrams": "mg",
    "ml": "ml",
    "ml.": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "l": "L",
    "l.": "L",
    "ltr": "L",
    "ltrs": "L",
    "liter": "L",
    "liters": "L",
    "litre": "L",
    "litres": "L",
    "cm": "cm",
    "m": "m",
    "metre": "m",
    "meter": "m",
    "metres": "m",
    "meters": "m",
    "piece": "pcs",
    "pieces": "pcs",
    "pc": "pcs",
    "pcs": "pcs",
    "units": "units",
    "unit": "units",
    "count": "units",
    "u": "units",
    "n": "units",
    "nos": "units",
    "no": "units",
}

# Multi-pack compound expressions e.g. "10 N x 82.7 g = 827 g", "6 N x 50 g = 300 g", "10 x 82.7g = 827g", "10 U x 82.7 g (827 g)"
NET_QTY_MULTIPACK_REGEX = re.compile(
    r"\b([0-9]+)\s*(?:N|U|UNITS?|PCS|PIECES?|NOS?)?\s*(?:[xX\*×])\s*"
    r"([0-9]+(?:[\.,][0-9]+)?)\s*(mg|kg|gms?|g|mL|ml|litres?|liters?|ltrs?|L|cm|meters?|metres?|m)?\s*"
    r"(?:=|EQUAL\s*TO|\()\s*([0-9]+(?:[\.,][0-9]+)?)\s*"
    r"(mg|kg|gms?|g|mL|ml|litres?|liters?|ltrs?|L|cm|meters?|metres?|m)?\)?\b",
    re.IGNORECASE,
)

# Explicit Net Quantity with anchor keyword
NET_QTY_EXPLICIT_REGEX = re.compile(
    r"\b(?:NET\s*(?:QUANTITY|QTY\.?|WEIGHT|WT\.?|VOLUME|VOL\.?|CONTENTS?)|N\.?W\.?|N\.?V\.?|NETWEIGHT|NETWT|NETQTY|NETVOL)\s*[:\.\-]?\s*"
    r"([0-9]+(?:[\.,][0-9]+)?)\s*"
    r"(?:(mg|kg|gms?|g|mL|ml|litres?|liters?|ltrs?|l|cm|meters?|metres?|m|pcs|pieces?|units?|count|nos?|u|n)\b)?",
    re.IGNORECASE,
)

# Standalone quantity (must have clear unit and not be in nutrition context)
NET_QTY_STANDALONE_REGEX = re.compile(
    r"\b([0-9]+(?:[\.,][0-9]+)?)\s*"
    r"(mg|kg|gms?|g|mL|ml|litres?|liters?|ltrs?|L|cm|meters?|metres?|m|pcs|pieces?|units?)\b",
    re.IGNORECASE,
)

# -------------------------------------------------------------------
# Manufacturer / Packer / Importer Patterns
# -------------------------------------------------------------------
MANUFACTURER_PREFIX_REGEX = re.compile(
    r"\b(?:MANUFACTURED\s*(?:&|AND)?\s*(?:MARKETED\s*)?BY|MFD\.?\s*BY|MFG\.?\s*BY|MANUFACTURED\s+AT|PRODUCED\s+BY)\b\s*[:\.\-]?\s*(.*)",
    re.IGNORECASE,
)

PACKER_PREFIX_REGEX = re.compile(
    r"\b(?:PACKED\s*(?:&|AND)?\s*BY|PKD\.?\s*BY|PACKAGED\s+BY)\b\s*[:\.\-]?\s*(.*)",
    re.IGNORECASE,
)

IMPORTER_PREFIX_REGEX = re.compile(
    r"\b(?:IMPORTED\s*(?:&|AND)?\s*BY|IMP\.?\s*BY|IMPORTER)\b\s*[:\.\-]?\s*(.*)",
    re.IGNORECASE,
)

MARKETED_PREFIX_REGEX = re.compile(
    r"\b(?:MARKETED\s*BY|MKTD\.?\s*BY)\b\s*[:\.\-]?\s*(.*)",
    re.IGNORECASE,
)

PINCODE_REGEX = re.compile(r"\b([1-9][0-9]{2}\s?[0-9]{3})\b")

ADDRESS_INDICATORS = [
    "PLOT", "ROAD", "STREET", "MARG", "NAGAR", "AREA", "ESTATE", "INDUSTRIAL", "IND.",
    "DIST", "DISTRICT", "TALUKA", "PO", "P.O.", "BOX", "SECTOR", "PHASE", "LTD", "PVT",
    "LIMITED", "PRIVATE", "MAHARASHTRA", "GUJARAT", "KARNATAKA", "DELHI", "TAMIL NADU",
    "HARYANA", "UTTAR PRADESH", "TELANGANA", "ANDHRA PRADESH", "PUNJAB", "RAJASTHAN",
    "KERALA", "WEST BENGAL", "MUMBAI", "PUNE", "BANGALORE", "CHENNAI", "HYDERABAD", "KOLKATA",
]

# -------------------------------------------------------------------
# Country of Origin Patterns
# -------------------------------------------------------------------
COUNTRY_ORIGIN_REGEX = re.compile(
    r"\b(?:COUNTRY\s+OF\s+ORIGIN|MADE\s+IN|PRODUCT\s+OF|MANUFACTURED\s+IN)\b\s*[:\.\-]?\s*([a-zA-Z\s]+)",
    re.IGNORECASE,
)

KNOWN_COUNTRIES = {
    "INDIA": "India",
    "IND": "India",
    "BHARAT": "India",
    "BANGLADESH": "Bangladesh",
    "CHINA": "China",
    "VIETNAM": "Vietnam",
    "THAILAND": "Thailand",
    "MALAYSIA": "Malaysia",
    "INDONESIA": "Indonesia",
    "SRI LANKA": "Sri Lanka",
    "NEPAL": "Nepal",
    "USA": "United States",
    "UNITED STATES": "United States",
    "UK": "United Kingdom",
    "UNITED KINGDOM": "United Kingdom",
    "GERMANY": "Germany",
    "FRANCE": "France",
    "ITALY": "Italy",
    "JAPAN": "Japan",
    "SOUTH KOREA": "South Korea",
    "KOREA": "South Korea",
    "AUSTRALIA": "Australia",
    "NEW ZEALAND": "New Zealand",
    "SINGAPORE": "Singapore",
    "UAE": "United Arab Emirates",
    "TURKEY": "Turkey",
    "SWITZERLAND": "Switzerland",
}

# -------------------------------------------------------------------
# Date Patterns (MFD, PKD, IMP, Best Before, EXP)
# -------------------------------------------------------------------
MFD_PREFIX_REGEX = re.compile(
    r"\b(?:MFD\.?\s*DATE|MFG\.?\s*DATE|MANUFACTURED\s*(?:ON|DATE)?|MFD\.?|MFG\.?)\b\s*[:\.\-]?\s*(.*)",
    re.IGNORECASE,
)

PKD_PREFIX_REGEX = re.compile(
    r"\b(?:PKD\.?\s*DATE|PACKED\s*(?:ON|DATE)?|PKD\.?|PACKING\s*DATE)\b\s*[:\.\-]?\s*(.*)",
    re.IGNORECASE,
)

IMP_DATE_PREFIX_REGEX = re.compile(
    r"\b(?:IMP\.?\s*DATE|IMPORTED\s*(?:ON|DATE)?|IMP\.?|IMPORT\s*DATE)\b\s*[:\.\-]?\s*(.*)",
    re.IGNORECASE,
)

BEST_BEFORE_PREFIX_REGEX = re.compile(
    r"\b(?:BEST\s+BEFORE|USE\s+BEFORE|B\.?B\.?)\b\s*[:\.\-]?\s*(.*)",
    re.IGNORECASE,
)

EXPIRY_PREFIX_REGEX = re.compile(
    r"\b(?:EXP\.?\s*DATE|EXPIRY\s*DATE|EXP\.?|EXPIRY|USE\s+BY)\b\s*[:\.\-]?\s*(.*)",
    re.IGNORECASE,
)

RELATIVE_DATE_REGEX = re.compile(
    r"\b(?:BEST\s+BEFORE\s+)?(\d+)\s*(MONTHS?|DAYS?|WEEKS?|YEARS?)\s+(?:FROM|OF)\s+(?:MFG\.?|MFD\.?|MANUFACTURE|PKD\.?|PACKING|PACKAGING)\b",
    re.IGNORECASE,
)

MONTH_NAMES_MAP = {
    "JAN": 1, "JANUARY": 1,
    "FEB": 2, "FEBRUARY": 2,
    "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4,
    "MAY": 5,
    "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7,
    "AUG": 8, "AUGUST": 8,
    "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11,
    "DEC": 12, "DECEMBER": 12,
}

# Date string regexes
DATE_DD_MM_YYYY_REGEX = re.compile(r"\b([0-3]?[0-9])[\/\-\.]([0-1]?[0-9])[\/\-\.](20[2-3][0-9]|19[0-9]{2})\b")
DATE_MM_YYYY_REGEX = re.compile(r"\b([0-1]?[0-9])[\/\-\.](20[2-3][0-9]|19[0-9]{2})\b")
DATE_MM_YY_REGEX = re.compile(r"\b([0-1]?[0-9])[\/\-\.]([2-3][0-9])\b")
DATE_MONTHNAME_YYYY_REGEX = re.compile(
    r"\b(JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUN(?:E)?|JUL(?:Y)?|AUG(?:UST)?|SEP(?:T(?:EMBER)?)?|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?)\s*[\/\-\.,]?\s*(20[2-3][0-9]|[2-3][0-9])\b",
    re.IGNORECASE,
)
DATE_DD_MONTHNAME_YYYY_REGEX = re.compile(
    r"\b([0-3]?[0-9])\s*[\/\-\.]?\s*(JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUN(?:E)?|JUL(?:Y)?|AUG(?:UST)?|SEP(?:T(?:EMBER)?)?|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?)\s*[\/\-\.,]?\s*(20[2-3][0-9]|[2-3][0-9])\b",
    re.IGNORECASE,
)

# -------------------------------------------------------------------
# Consumer Care Patterns
# -------------------------------------------------------------------
CONSUMER_CARE_HEADER_REGEX = re.compile(
    r"\b(?:CONSUMER\s*(?:CARE|COMPLAINTS?|GRIEVANCE|FEEDBACK)|"
    r"CUSTOMER\s*(?:CARE|SERVICE|SUPPORT|GRIEVANCE)|"
    r"FOR\s+(?:FEEDBACK|COMPLAINTS?|QUERIES)|"
    r"CONTACT\s+(?:US|CONSUMER\s*CARE|CUSTOMER\s*CARE)|"
    r"CARE\s*LINE|HELPLINE)\b",
    re.IGNORECASE,
)

PHONE_CONTACT_PREFIX_REGEX = re.compile(
    r"\b(?:TEL|PH(?:ONE)?|MOB(?:ILE)?|TOLL[\s-]*FREE|CALL|HELPLINE|CUSTOMER\s*CARE|CONSUMER\s*CARE|CARE\s*LINE|CONTACT|FEEDBACK)\b",
    re.IGNORECASE,
)

# Toll Free: 1800-4254449, 1-800-4254449, 1800-111-222, 1800 425 4449
# Mobile: +91 9876543210, 9876543210
# Landline: 080-23456789, 022 12345678
PHONE_REGEX = re.compile(
    r"(?:(?:TEL|PH(?:ONE)?|MOB(?:ILE)?|TOLL[\s-]*FREE|CALL|HELPLINE)\s*[:\.\-]?\s*)?"
    r"(\+?91[\s\-]?)?(1800[\s\-]?[0-9]{3}[\s\-]?[0-9]{3,4}|1[\s\-]800[\s\-]?[0-9]{3}[\s\-]?[0-9]{3,4}|[6-9][0-9]{4}[\s\-]?[0-9]{5}|[6-9][0-9]{9}|0[0-9]{2,4}[\s\-]?[0-9]{6,8})",
    re.IGNORECASE,
)

EMAIL_REGEX = re.compile(
    r"([a-zA-Z0-9_.+-]+(?:\s*@\s*|\s*\[at\]\s*)[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
    re.IGNORECASE,
)

# -------------------------------------------------------------------
# Batch / Lot Number Patterns
# -------------------------------------------------------------------
BATCH_REGEX = re.compile(
    r"\b(?:BATCH\s*(?:NO\.?|NUMBER|CODE)?|LOT\s*(?:NO\.?|NUMBER|CODE)?|B\.?\s*NO\.?|L\.?\s*NO\.?|BN\.?)\b\s*[:\.\-]?\s*(.*)",
    re.IGNORECASE,
)

# -------------------------------------------------------------------
# Commodity / Generic Product Name Patterns
# -------------------------------------------------------------------
COMMODITY_PREFIX_REGEX = re.compile(
    r"\b(?:GENERIC\s+NAME|COMMODITY\s+NAME|COMMODITY|PRODUCT\s+NAME)\b\s*[:\.\-]?\s*([a-zA-Z0-9\s,\-\/]+?)(?=\n|\r|$)",
    re.IGNORECASE,
)
