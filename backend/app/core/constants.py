"""Application constants and default configuration parameters."""

# Confidence Thresholds
DEFAULT_CONFIDENCE_THRESHOLD_PASS = 0.85
DEFAULT_CONFIDENCE_THRESHOLD_REVIEW = 0.60

# Image Quality Thresholds (Placeholders for CV pipeline)
MIN_BLUR_LAPLACIAN_VAR = 100.0
MAX_GLARE_PIXEL_RATIO = 0.15
MIN_IMAGE_WIDTH_PX = 800
MIN_IMAGE_HEIGHT_PX = 600

# Default Rule Engine Version
DEFAULT_RULE_SET_VERSION = "2011.1.0"

# Application Metadata
APP_TITLE = "LegalMetrix AI API"
APP_DESCRIPTION = (
    "Compliance verification system for packaged commodities under the "
    "Legal Metrology (Packaged Commodities) Rules, 2011."
)
APP_VERSION = "0.1.0"

# Route and Role Matrix definitions
ROLE_PERMISSIONS = {
    "ADMIN": ["dashboard", "products", "inspections", "reports", "rules", "audit", "users"],
    "INSPECTOR": ["dashboard", "new_scan", "products", "inspections", "reports"],
    "REVIEWER": ["dashboard", "products", "inspections", "reviews", "reports"],
}
