import re
MRP_EXPLICIT_REGEX = re.compile(
    r"\b(?:MAXIMUM\s+RETAIL\s+PRICE|MAX\.?\s+RETAIL\s+PRICE|RETAIL\s+(?:SALE\s+)?PRICE|M\.?R\.?P\.?[E]?)\b\s*[:.\-]?\s*"
    r"(?:(?:₹|\bRS\.?|\bINR)\s*)?"
    r"([0-9]{1,7}(?:[.,][0-9]{1,2})?)"
    r"(?:\s*(?:\/-|\/|INCL|INCLUSIVE))?",
    re.IGNORECASE,
)
text = 'Maximum Retail Price ₹1,299'
match = MRP_EXPLICIT_REGEX.search(text)
if match:
    print('Raw amount:', match.group(1))

text2 = 'MRP: ₹3,500.00 (inclusive of taxes)'
match2 = MRP_EXPLICIT_REGEX.search(text2)
if match2:
    print('Raw amount 2:', match2.group(1))
