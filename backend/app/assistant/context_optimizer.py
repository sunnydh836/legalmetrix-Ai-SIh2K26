"""
Context Optimizer & Token-Saving Dynamic Chunking Engine for LegalMetrix AI Assistant.

Ensures minimal token consumption and maximum response accuracy by:
1. Pruning conversation history to a sliding window of the last 3-4 turns.
2. Semantic, intent-driven extraction chunking (sending only relevant scan context).
3. Filtering raw declarations and metrics to only those matching the user's inquiry intent.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.assistant.intent_classifier import IntentClassificationResult, IntentClassifier, IntentType
from app.assistant.schemas import ChatMessage


class ContextOptimizer:
    """Optimizes context payload before sending to the LLM to drastically reduce token costs and eliminate noise."""

    MAX_HISTORY_TURNS: int = 4  # Keep last 3-4 chat turns (6-8 messages max)
    MAX_HISTORY_MSG_LEN: int = 400  # Truncate older verbose messages

    @classmethod
    def prune_history(cls, history: List[ChatMessage]) -> List[Dict[str, str]]:
        """
        Keeps only the last 3-4 turns and truncates overly verbose prior turns.
        """
        if not history:
            return []

        recent = history[- (cls.MAX_HISTORY_TURNS * 2):]
        pruned = []

        for msg in recent:
            content = msg.content.strip()
            if len(content) > cls.MAX_HISTORY_MSG_LEN:
                content = content[:cls.MAX_HISTORY_MSG_LEN] + "... [truncated]"

            pruned.append({
                "role": "user" if msg.role.lower() in ["user", "human"] else "assistant",
                "content": content
            })

        return pruned

    @classmethod
    def filter_scan_context(
        cls,
        user_query: str,
        scan_data: Optional[Dict[str, Any]],
        quality_metrics: Optional[List[Dict[str, Any]]],
        declarations: Optional[List[Dict[str, Any]]],
        findings: Optional[List[Dict[str, Any]]],
        intent_result: Optional[IntentClassificationResult] = None,
    ) -> Tuple[str, int]:
        """
        Selectively chunks and extracts only the relevant domain context
        matching the classified intent and entities.
        Returns: (filtered_context_string, estimated_tokens_saved)
        """
        if not scan_data:
            return "", 0

        # Classify intent if not already provided
        product = scan_data.get("product") or {}
        p_name = product.get("name") or scan_data.get("scan_code") or "Unknown Product"
        brand = product.get("brand") or ""
        status = scan_data.get("status") or "CREATED"

        if intent_result is None:
            intent_result = IntentClassifier.classify(
                message=user_query,
                history=[],
                active_product_name=p_name if p_name != "Unknown Product" else None,
            )

        intent = intent_result.intent
        target_fields = set(intent_result.target_fields)
        panel_ref = intent_result.panel_referenced

        context_parts: List[str] = []
        tokens_saved_estimate = 0

        # Base compact header
        base_header = f"Active Product: {p_name}" + (f" ({brand})" if brand else "") + f" | Session Status: {status}"

        # 1. Greeting or Chitchat / Politeness -> Minimalist Context
        if intent in [IntentType.GREETING_OR_CHITCHAT, IntentType.POLITENESS_OR_THANKS]:
            context_parts.append(base_header)
            # Estimate tokens saved by dropping declarations, quality metrics, findings
            saved_decls = len(declarations or []) * 30
            saved_quality = len(quality_metrics or []) * 25
            saved_findings = len(findings or []) * 20
            tokens_saved_estimate = saved_decls + saved_quality + saved_findings + 150
            return "\n".join(context_parts), tokens_saved_estimate

        # 2. System Navigation or Pure Legal Question without active scan focus
        if intent in [IntentType.SYSTEM_NAVIGATION_HELP, IntentType.LEGAL_REGULATION_INQUIRY] and not intent_result.requires_scan_data:
            tokens_saved_estimate = (len(declarations or []) * 30) + (len(quality_metrics or []) * 25) + 120
            return "", tokens_saved_estimate

        # For scan-focused inquiries, add standard header
        context_parts.append(base_header)

        # 3. Image Quality & Camera Diagnostics
        if intent == IntentType.IMAGE_QUALITY_DIAGNOSTIC:
            if quality_metrics:
                context_parts.append("--- Image Quality Diagnostics ---")
                for idx, qm in enumerate(quality_metrics[:5]):
                    q_stat = qm.get("quality_status", "UNKNOWN")
                    blur = qm.get("blur_score", 0.0)
                    glare = qm.get("glare_score", 0.0)
                    panel = qm.get("panel_type") or f"Panel {idx + 1}"
                    warnings = qm.get("warnings", [])

                    # Highlight if this matches referenced panel
                    prefix = "▶ " if panel_ref and panel_ref in str(panel).upper() else "• "
                    context_parts.append(
                        f"{prefix}{panel}: Status={q_stat}, BlurScore={blur:.1f} (min 100), GlareRatio={(glare * 100):.1f}% (max 5.0%){', Flags: ' + str(warnings) if warnings else ''}"
                    )
            # Drop all declarations and findings
            tokens_saved_estimate += (len(declarations or []) * 30) + (len(findings or []) * 20)
            return "\n".join(context_parts), tokens_saved_estimate

        # 4. Specific Declaration Check
        if intent == IntentType.SPECIFIC_DECLARATION_CHECK and declarations:
            matching_decls = []
            for d in declarations:
                dtype = (d.get("declaration_type") or "").upper()
                raw_text = d.get("raw_text", "")
                conf = d.get("confidence", 0.0)
                rev = d.get("review_status", "UNREVIEWED")

                matched = False
                if "mrp" in target_fields and "MRP" in dtype:
                    matched = True
                elif "net_quantity" in target_fields and "QUANTITY" in dtype:
                    matched = True
                elif "manufacturer" in target_fields and any(x in dtype for x in ["MANUFACTURER", "PACKER", "IMPORTER", "ORIGIN"]):
                    matched = True
                elif "dates" in target_fields and any(x in dtype for x in ["DATE", "EXPIRY", "BEFORE"]):
                    matched = True
                elif "consumer_care" in target_fields and "CONSUMER_CARE" in dtype:
                    matched = True
                elif "fssai" in target_fields and "FSSAI" in dtype:
                    matched = True

                if matched:
                    matching_decls.append(f"• [{dtype}] '{raw_text}' (Confidence: {conf:.2f}, Review: {rev})")

            if matching_decls:
                context_parts.append("--- Extracted Target Declarations ---")
                context_parts.extend(matching_decls[:6])
                # Tokens saved from dropped non-matching declarations
                tokens_saved_estimate += max(0, (len(declarations) - len(matching_decls)) * 30)
            else:
                context_parts.append(f"*(Note: No extracted declaration matched target fields: {', '.join(target_fields)})*")

            # Check matching rule findings
            if findings:
                matching_findings = []
                for f in findings:
                    rule_code = f.get("rule_code", "")
                    if any(tf.upper() in rule_code for tf in target_fields) or f.get("status") in ["FAIL", "REVIEW"]:
                        matching_findings.append(f"• Rule {rule_code} [{f.get('status')}]: {f.get('message', '')}")
                if matching_findings:
                    context_parts.append("--- Applicable Rule Findings ---")
                    context_parts.extend(matching_findings[:3])

            # Drop quality metrics
            tokens_saved_estimate += len(quality_metrics or []) * 25
            return "\n".join(context_parts), tokens_saved_estimate

        # 5. Product Compliance Overview / General Knowledge
        if declarations:
            context_parts.append("--- Extracted Declarations Overview ---")
            for d in declarations[:8]:
                dtype = (d.get("declaration_type") or "").upper()
                raw = d.get("raw_text", "")
                conf = d.get("confidence", 0.0)
                context_parts.append(f"• [{dtype}]: '{raw[:70]}' (Conf: {conf:.2f})")
            if len(declarations) > 8:
                tokens_saved_estimate += (len(declarations) - 8) * 30

        if findings:
            violations = [f for f in findings if f.get("status") in ["FAIL", "REVIEW"]]
            if violations:
                context_parts.append("--- Rule Engine Flags & Issues ---")
                for v in violations[:5]:
                    context_parts.append(f"• Rule {v.get('rule_code')} [{v.get('status')}]: {v.get('message', '')}")
                tokens_saved_estimate += max(0, (len(findings) - min(5, len(violations))) * 20)

        return "\n".join(context_parts), tokens_saved_estimate
