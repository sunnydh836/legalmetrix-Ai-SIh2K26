"""
Intent Classifier & Query Reformulation Engine for LegalMetrix AI Assistant.

Analyzes user queries, conversation history, and attached modalities to:
1. Identify high-level user intent (e.g., GREETING, SPECIFIC_DECLARATION_CHECK, IMAGE_QUALITY, REGULATION_INQUIRY, SCAN_OVERVIEW, SYSTEM_HELP).
2. Extract targeted declaration entities, panel references, and rule codes.
3. Perform conversational coreference resolution and query rewriting.
"""

from enum import Enum
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.assistant.schemas import ChatMessage


class IntentType(str, Enum):
    GREETING_OR_CHITCHAT = "GREETING_OR_CHITCHAT"
    PRODUCT_COMPLIANCE_OVERVIEW = "PRODUCT_COMPLIANCE_OVERVIEW"
    SPECIFIC_DECLARATION_CHECK = "SPECIFIC_DECLARATION_CHECK"
    IMAGE_QUALITY_DIAGNOSTIC = "IMAGE_QUALITY_DIAGNOSTIC"
    LEGAL_REGULATION_INQUIRY = "LEGAL_REGULATION_INQUIRY"
    SYSTEM_NAVIGATION_HELP = "SYSTEM_NAVIGATION_HELP"
    POLITENESS_OR_THANKS = "POLITENESS_OR_THANKS"
    GENERAL_KNOWLEDGE = "GENERAL_KNOWLEDGE"


class IntentClassificationResult(BaseModel):
    intent: IntentType = Field(..., description="Classified intent of the user inquiry")
    target_fields: List[str] = Field(default_factory=list, description="Target declaration fields (e.g., ['mrp', 'net_quantity'])")
    panel_referenced: Optional[str] = Field(None, description="Specific package panel if mentioned (e.g., FRONT, BACK, SIDE)")
    rewritten_query: str = Field(..., description="Self-contained query with conversational pronouns resolved")
    requires_scan_data: bool = Field(False, description="Whether active scan session context is needed to answer")
    requires_legal_rules: bool = Field(False, description="Whether formal LMR 2011 rule text is needed")
    confidence: float = Field(default=1.0, description="Confidence in intent classification (0.0 to 1.0)")


class IntentClassifier:
    """
    Intelligent Intent & Entity Extractor.
    Operates as a high-speed semantic analyzer with zero-latency regex/pattern matching
    and conversational reference tracking.
    """

    # Keyword clusters for declaration entity extraction (matched with whole-word boundaries)
    DECLARATION_FIELD_MAP = {
        "mrp": [
            r"\bmrp\b", r"\bprice\b", r"\bpricing\b", r"\bcost\b", r"\btax\b", r"\btaxes\b",
            r"\brate\b", r"\brs\.?\b", r"₹", r"\brupees?\b", r"\bretail price\b",
            r"\busp\b", r"\bunit sale price\b"
        ],
        "net_quantity": [
            r"\bquantity\b", r"\bqty\b", r"\bweight\b", r"\bvolume\b", r"\bnet\b",
            r"\bgrams?\b", r"\bgm\b", r"\bg\b", r"\bkg\b", r"\bkgs\b", r"\bkilograms?\b",
            r"\bml\b", r"\bliters?\b", r"\blitres?\b", r"\bl\b", r"\bnet wt\b",
            r"\bnet weight\b", r"\bnet contents\b", r"\bcount\b", r"\bunits?\b"
        ],
        "manufacturer": [
            r"\bmanufactur(er|ed|ing)\b", r"\bmfg\b", r"\bpacker\b", r"\bpacked by\b",
            r"\bimporter\b", r"\bimported by\b", r"\baddress\b", r"\bcompany\b",
            r"\bmfg address\b", r"\borigin\b", r"\bcountry of origin\b", r"\bmade in\b"
        ],
        "dates": [
            r"\bdates?\b", r"\bexpiry\b", r"\bexp\.?\b", r"\bmfd\.?\b", r"\bpkd\.?\b",
            r"\bpacking date\b", r"\bmfg date\b", r"\bbest before\b", r"\buse by\b",
            r"\bshelf life\b"
        ],
        "consumer_care": [
            r"\bconsumer\b", r"\bcare\b", r"\bhelpline\b", r"\bemail\b", r"\bcomplaint\b",
            r"\bfeedback\b", r"\bcontact\b", r"\btoll\s*free\b", r"\bgrievance\b",
            r"\bcustomer care\b"
        ],
        "fssai": [
            r"\bfssai\b", r"\blicense\b", r"\blic no\b", r"\bfood safety\b", r"\bfssai no\b"
        ],
    }

    # Panels
    PANEL_KEYWORDS = {
        "FRONT": [r"\bfront\b", r"\bpdp\b", r"\bprincipal display\b"],
        "BACK": [r"\bback\b", r"\brear\b"],
        "SIDE": [r"\bside\b", r"\bsides\b", r"\blateral\b"],
        "TOP": [r"\btop\b"],
        "BOTTOM": [r"\bbottom\b", r"\bbase\b"],
    }

    # Quality & Diagnostics keywords
    QUALITY_PATTERNS = [
        r"\bblur(ry)?\b", r"\bsharpness\b", r"\bglare\b", r"\breflection\b", r"\bshiny\b",
        r"\bspecular\b", r"\bcamera\b", r"\bphoto\b", r"\bimage\b", r"\bquality\b",
        r"\brecapture\b", r"\blight(ing)?\b", r"\bflash\b", r"\bfocus\b",
        r"\bresolution\b", r"\blow res\b", r"\brescan\b", r"\bretake\b"
    ]

    # Greeting patterns
    GREETING_PATTERNS = [
        r"\bhi\b", r"\bhello\b", r"\bhey\b", r"\bhii+\b", r"\bheyy+\b", r"\bnamaste\b",
        r"\bgood\s+(morning|afternoon|evening)\b", r"\bhowdy\b", r"\bgreetings\b"
    ]

    # Politeness / Gratitude patterns
    POLITENESS_PATTERNS = [
        r"\bthanks?\b", r"\bthank\s+you\b", r"\bthx\b", r"\bok(ay)?\b", r"\bgot\s+it\b",
        r"\bcool\b", r"\bgreat\b", r"\bawesome\b", r"\bbye\b", r"\bgoodbye\b", r"\bcheers\b",
        r"\bperfect\b", r"\bdone\b"
    ]

    # Navigation / Capabilities
    CAPABILITY_PATTERNS = [
        r"\bwho are you\b", r"\bwhat can you do\b", r"\bwhat is your role\b", r"\bhelp me\b",
        r"\bhow to use\b", r"\bhow do i\b", r"\bguide me\b", r"\bwhat are your features\b",
        r"\bsystem help\b", r"\bworkflow\b", r"\bhow to scan\b"
    ]

    # Legal Metrology / Rules keywords
    LEGAL_RULE_PATTERNS = [
        r"\brule\s*\d+\b", r"\brules?\b", r"\bact\b", r"\bsection\s*\d+\b", r"\blmr\b",
        r"\blegal metrology\b", r"\blaw\b", r"\bregulation\b", r"\bpenalty\b",
        r"\bviolation\b", r"\bclause\b", r"\bsub-rule\b", r"\bprovisions?\b", r"\bmandatory\b"
    ]

    @classmethod
    def classify(
        cls,
        message: str,
        history: Optional[List[ChatMessage]] = None,
        active_product_name: Optional[str] = None,
    ) -> IntentClassificationResult:
        """
        Classifies intent and extracts relevant entities and rewritten query.
        """
        raw_query = message.strip()
        query_lower = raw_query.lower()
        words = re.findall(r"\b\w+\b", query_lower)
        word_count = len(words)

        # 1. Extract Target Fields with word boundary matching
        target_fields = []
        for field, patterns in cls.DECLARATION_FIELD_MAP.items():
            for pat in patterns:
                if re.search(pat, query_lower):
                    target_fields.append(field)
                    break

        # 2. Extract Panel Reference
        panel_ref = None
        for panel, patterns in cls.PANEL_KEYWORDS.items():
            for pat in patterns:
                if re.search(pat, query_lower):
                    panel_ref = panel
                    break
            if panel_ref:
                break

        # 3. Detect Intent

        # Priority A: Politeness / Gratitude (short messages)
        is_polite = any(re.search(pat, query_lower) for pat in cls.POLITENESS_PATTERNS)
        if is_polite and word_count <= 4 and not target_fields:
            return IntentClassificationResult(
                intent=IntentType.POLITENESS_OR_THANKS,
                target_fields=[],
                panel_referenced=None,
                rewritten_query=raw_query,
                requires_scan_data=False,
                requires_legal_rules=False,
                confidence=0.98,
            )

        # Priority B: Greetings (short messages without explicit specific declaration questions)
        is_greeting = any(re.search(pat, query_lower) for pat in cls.GREETING_PATTERNS)
        if is_greeting and word_count <= 5 and not target_fields:
            return IntentClassificationResult(
                intent=IntentType.GREETING_OR_CHITCHAT,
                target_fields=[],
                panel_referenced=None,
                rewritten_query=raw_query,
                requires_scan_data=bool(active_product_name),
                requires_legal_rules=False,
                confidence=0.99,
            )

        # Priority C: System Navigation / Capabilities
        if any(re.search(pat, query_lower) for pat in cls.CAPABILITY_PATTERNS) and not target_fields:
            return IntentClassificationResult(
                intent=IntentType.SYSTEM_NAVIGATION_HELP,
                target_fields=[],
                panel_referenced=None,
                rewritten_query=raw_query,
                requires_scan_data=False,
                requires_legal_rules=False,
                confidence=0.95,
            )

        # Priority D: Image Quality & Camera Diagnostics
        if any(re.search(pat, query_lower) for pat in cls.QUALITY_PATTERNS) and not (target_fields and "mrp" in target_fields and word_count > 8):
            return IntentClassificationResult(
                intent=IntentType.IMAGE_QUALITY_DIAGNOSTIC,
                target_fields=target_fields,
                panel_referenced=panel_ref,
                rewritten_query=raw_query,
                requires_scan_data=True,
                requires_legal_rules=False,
                confidence=0.92,
            )

        # Priority E: Pure Legal Regulation Inquiry (e.g. "What are the mandatory provisions under Rule 6 of LMR 2011?")
        is_legal_inquiry = any(re.search(pat, query_lower) for pat in cls.LEGAL_RULE_PATTERNS)
        if is_legal_inquiry and not active_product_name and not ("this" in query_lower or "my" in query_lower or "it" in query_lower):
            # General legal question without active scan focus
            return IntentClassificationResult(
                intent=IntentType.LEGAL_REGULATION_INQUIRY,
                target_fields=target_fields,
                panel_referenced=panel_ref,
                rewritten_query=raw_query,
                requires_scan_data=False,
                requires_legal_rules=True,
                confidence=0.94,
            )

        # Priority F: Specific Declaration Checks
        if target_fields:
            rewritten = cls._rewrite_query_with_context(raw_query, history, active_product_name, target_fields)
            return IntentClassificationResult(
                intent=IntentType.SPECIFIC_DECLARATION_CHECK,
                target_fields=target_fields,
                panel_referenced=panel_ref,
                rewritten_query=rewritten,
                requires_scan_data=True,
                requires_legal_rules=True,
                confidence=0.95,
            )

        # Priority G: General Legal Metrology / Rules Inquiry
        if is_legal_inquiry:
            return IntentClassificationResult(
                intent=IntentType.LEGAL_REGULATION_INQUIRY,
                target_fields=[],
                panel_referenced=panel_ref,
                rewritten_query=raw_query,
                requires_scan_data=False,
                requires_legal_rules=True,
                confidence=0.90,
            )

        # Priority H: Scan Overview / Compliance Summary
        overview_terms = [
            r"\bsummary\b", r"\boverview\b", r"\bstatus\b", r"\bcheck\b", r"\bcompliant\b",
            r"\bfindings\b", r"\breport\b", r"\breview\b", r"\bis this legal\b",
            r"\bcan i sell\b", r"\bpass\b", r"\bfail\b", r"\bscore\b"
        ]
        if any(re.search(pat, query_lower) for pat in overview_terms) or (active_product_name and active_product_name.lower() in query_lower):
            rewritten = cls._rewrite_query_with_context(raw_query, history, active_product_name, [])
            return IntentClassificationResult(
                intent=IntentType.PRODUCT_COMPLIANCE_OVERVIEW,
                target_fields=[],
                panel_referenced=panel_ref,
                rewritten_query=rewritten,
                requires_scan_data=True,
                requires_legal_rules=True,
                confidence=0.88,
            )

        # Fallback: General Knowledge
        return IntentClassificationResult(
            intent=IntentType.GENERAL_KNOWLEDGE,
            target_fields=[],
            panel_referenced=panel_ref,
            rewritten_query=raw_query,
            requires_scan_data=bool(active_product_name),
            requires_legal_rules=True,
            confidence=0.75,
        )

    @classmethod
    def _rewrite_query_with_context(
        cls,
        query: str,
        history: Optional[List[ChatMessage]],
        active_product_name: Optional[str],
        target_fields: List[str],
    ) -> str:
        """
        Resolves pronouns like 'it', 'this product', 'that field' using conversational history.
        """
        if not active_product_name:
            return query

        query_clean = query.strip()
        pronoun_pattern = r"\b(it|its|this product|this item|the product|that product)\b"

        if re.search(pronoun_pattern, query_clean, flags=re.IGNORECASE):
            rewritten = re.sub(
                pronoun_pattern,
                f"'{active_product_name}'",
                query_clean,
                flags=re.IGNORECASE,
            )
            return rewritten

        return query_clean
