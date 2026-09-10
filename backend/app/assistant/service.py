"""
LegalMetrix AI Assistant — Core Service with Dynamic Intent Routing, Modular System Prompting, and Streaming SSE.
"""

import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from app.assistant.context_optimizer import ContextOptimizer
from app.assistant.intent_classifier import IntentClassificationResult, IntentClassifier, IntentType
from app.assistant.prompts import SYSTEM_PROMPT, compose_adaptive_system_prompt
from app.assistant.schemas import ChatMessage, ChatResponse, ChatStreamRequest
from app.core.config import settings

logger = logging.getLogger(__name__)


class AssistantService:
    """Enterprise AI Assistant Service supporting Gemini, OpenAI, Groq, and Smart Local SSE Streaming with Intent-Driven Routing."""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        self.gemini_key = settings.GEMINI_API_KEY
        self.openai_key = settings.OPENAI_API_KEY
        self.groq_key = settings.GROQ_API_KEY

    def _determine_active_provider(self) -> str:
        """Auto-detects active provider based on environment keys."""
        if self.provider != "auto":
            return self.provider

        if self.gemini_key:
            return "gemini"
        elif self.groq_key:
            return "groq"
        elif self.openai_key:
            return "openai"
        return "mock"

    async def stream_chat(
        self,
        request: ChatStreamRequest,
        scan_context_str: str = "",
        raw_scan_data: Optional[Dict[str, Any]] = None,
        tokens_saved: int = 0,
        intent_result: Optional[IntentClassificationResult] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Yields SSE chunks: `data: {"text": "...", "done": false, "intent": "...", "tokens_saved": ...}\n\n`
        """
        active_provider = self._determine_active_provider()
        pruned_history = ContextOptimizer.prune_history(request.history or [])

        # 1. Resolve Intent Classification
        product_name = None
        if raw_scan_data and raw_scan_data.get("product"):
            product_name = raw_scan_data["product"].get("name") or raw_scan_data.get("scan_code")

        if intent_result is None:
            intent_result = IntentClassifier.classify(
                message=request.message,
                history=request.history,
                active_product_name=product_name,
            )

        # 2. Dynamic Modular System Prompt Composition
        system_instruction = compose_adaptive_system_prompt(
            intent=intent_result.intent,
            user_role=request.user_role or "INSPECTOR",
            scan_context_str=scan_context_str,
        )

        # -------------------------------------------------------------
        # Console Logging: Log prompt, context, and intent before dispatch
        # -------------------------------------------------------------
        print("\n" + "=" * 80)
        print("🤖 [LEGALMETRIX AI ASSISTANT] — INCOMING INPUT PROMPT & DYNAMIC INTENT LOG")
        print("=" * 80)
        print(f"📌 Active Provider     : {active_provider.upper()} (Model: {self.model})")
        print(f"🎯 Detected Intent     : {intent_result.intent.value} (Conf: {intent_result.confidence:.2f})")
        print(f"🏷️  Target Fields       : {intent_result.target_fields or 'None'}")
        if intent_result.panel_referenced:
            print(f"🖼️  Panel Referenced    : {intent_result.panel_referenced}")
        print(f"👤 User Role           : {request.user_role or 'INSPECTOR'}")
        print(f"🔍 Scan Session ID      : {request.scan_id or 'None'}")
        print(f"💬 Raw User Prompt     : {request.message}")
        if intent_result.rewritten_query != request.message:
            print(f"🔄 Rewritten Query     : {intent_result.rewritten_query}")
        print(f"🖼️  Image Attachment    : {'Yes (Base64 attached)' if request.image_base64 else 'No'}")
        print(f"📜 History Turns Sent  : {len(pruned_history)} message(s)")
        print(f"💡 Tokens Saved Est.   : ~{tokens_saved} tokens")
        if scan_context_str:
            print("-" * 80)
            print("📦 [INJECTED ADAPTIVE SCAN EVIDENCE CONTEXT]:")
            print(scan_context_str)
        print("-" * 80)
        print("📋 [DYNAMIC ASSEMBLED SYSTEM INSTRUCTION]:")
        print(system_instruction[:450] + ("\n... [remaining instructions omitted for brevity]" if len(system_instruction) > 450 else ""))
        print("=" * 80 + "\n")

        # Substitute rewritten query into request for generation if disambiguated
        effective_request = request
        if intent_result.rewritten_query and intent_result.rewritten_query != request.message:
            effective_request = request.model_copy(update={"message": intent_result.rewritten_query})

        try:
            if active_provider == "gemini" and self.gemini_key:
                async for chunk in self._stream_gemini(effective_request, system_instruction, pruned_history, tokens_saved, intent_result):
                    yield chunk
            elif active_provider == "groq" and self.groq_key:
                async for chunk in self._stream_openai_compatible(
                    "https://api.groq.com/openai/v1/chat/completions",
                    self.groq_key,
                    self.model or "llama-3.1-8b-instant",
                    effective_request,
                    system_instruction,
                    pruned_history,
                    tokens_saved,
                    intent_result,
                ):
                    yield chunk
            elif active_provider == "openai" and self.openai_key:
                async for chunk in self._stream_openai_compatible(
                    "https://api.openai.com/v1/chat/completions",
                    self.openai_key,
                    self.model or "gpt-4o-mini",
                    effective_request,
                    system_instruction,
                    pruned_history,
                    tokens_saved,
                    intent_result,
                ):
                    yield chunk
            else:
                # Intelligent Local Domain Fallback
                async for chunk in self._stream_smart_fallback(effective_request, raw_scan_data, tokens_saved, intent_result):
                    yield chunk
        except Exception as e:
            logger.error(f"Error in LLM stream: {str(e)}", exc_info=True)
            error_data = json.dumps({
                "text": f"\n\n*(Notice: Remote {active_provider} connection unavailable. Switched to LegalMetrix offline copilot)*\n\n",
                "done": False,
                "intent": intent_result.intent.value,
            })
            yield f"data: {error_data}\n\n"
            async for chunk in self._stream_smart_fallback(effective_request, raw_scan_data, tokens_saved, intent_result):
                yield chunk

    async def _stream_gemini(
        self,
        request: ChatStreamRequest,
        system_instruction: str,
        pruned_history: List[Dict[str, str]],
        tokens_saved: int,
        intent_result: IntentClassificationResult,
    ) -> AsyncGenerator[str, None]:
        """Stream via Google Gemini REST API (supports Multimodal base64 image)."""
        model_name = self.model or "gemini-3.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?key={self.gemini_key}&alt=sse"

        contents = []
        for h in pruned_history:
            role = "user" if h["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": h["content"]}]})

        current_user_parts: List[Dict[str, Any]] = [{"text": request.message}]

        if request.image_base64:
            clean_b64 = request.image_base64
            if "," in clean_b64:
                clean_b64 = clean_b64.split(",", 1)[1]
            current_user_parts.append({
                "inlineData": {
                    "mimeType": request.image_mime_type or "image/jpeg",
                    "data": clean_b64,
                }
            })

        contents.append({"role": "user", "parts": current_user_parts})

        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1024,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, json=payload, headers={"Content-Type": "application/json"}) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise RuntimeError(f"Gemini API returned status {response.status_code}: {error_body.decode('utf-8', errors='ignore')}")

                async for raw_line in response.aiter_lines():
                    if not raw_line or not raw_line.startswith("data: "):
                        continue
                    json_str = raw_line[6:].strip()
                    try:
                        gemini_chunk = json.loads(json_str)
                        candidates = gemini_chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for p in parts:
                                text_token = p.get("text", "")
                                if text_token:
                                    sse_payload = json.dumps({
                                        "text": text_token,
                                        "done": False,
                                        "tokens_saved": tokens_saved,
                                        "intent": intent_result.intent.value,
                                    })
                                    yield f"data: {sse_payload}\n\n"
                    except json.JSONDecodeError:
                        continue

        yield f"data: {json.dumps({'text': '', 'done': True, 'tokens_saved': tokens_saved, 'intent': intent_result.intent.value})}\n\n"

    async def _stream_openai_compatible(
        self,
        endpoint_url: str,
        api_key: str,
        model: str,
        request: ChatStreamRequest,
        system_instruction: str,
        pruned_history: List[Dict[str, str]],
        tokens_saved: int,
        intent_result: IntentClassificationResult,
    ) -> AsyncGenerator[str, None]:
        """Stream via standard OpenAI-compatible completions endpoint (OpenAI / Groq)."""
        messages = [{"role": "system", "content": system_instruction}]
        for h in pruned_history:
            messages.append({"role": h["role"], "content": h["content"]})

        if request.image_base64 and ("gpt-4" in model or "vision" in model):
            b64_url = (
                request.image_base64
                if request.image_base64.startswith("data:")
                else f"data:{request.image_mime_type or 'image/jpeg'};base64,{request.image_base64}"
            )
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": request.message},
                    {"type": "image_url", "image_url": {"url": b64_url}},
                ],
            })
        else:
            messages.append({"role": "user", "content": request.message})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": 0.3,
            "max_tokens": 1024,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", endpoint_url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    err_txt = await response.aread()
                    raise RuntimeError(f"LLM API returned {response.status_code}: {err_txt.decode('utf-8', errors='ignore')}")

                async for raw_line in response.aiter_lines():
                    if not raw_line or not raw_line.startswith("data: "):
                        continue
                    data_body = raw_line[6:].strip()
                    if data_body == "[DONE]":
                        break
                    try:
                        chunk_json = json.loads(data_body)
                        choices = chunk_json.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                sse_payload = json.dumps({
                                    "text": token,
                                    "done": False,
                                    "tokens_saved": tokens_saved,
                                    "intent": intent_result.intent.value,
                                })
                                yield f"data: {sse_payload}\n\n"
                    except json.JSONDecodeError:
                        continue

        yield f"data: {json.dumps({'text': '', 'done': True, 'tokens_saved': tokens_saved, 'intent': intent_result.intent.value})}\n\n"

    async def _stream_smart_fallback(
        self,
        request: ChatStreamRequest,
        raw_scan_data: Optional[Dict[str, Any]],
        tokens_saved: int,
        intent_result: IntentClassificationResult,
    ) -> AsyncGenerator[str, None]:
        """
        Context-aware offline generator that uses classified user intent and entities
        to synthesize natural, clean regulatory guidance.
        """
        intent = intent_result.intent
        target_fields = set(intent_result.target_fields)

        # Extract product & declaration info if active
        product_info = raw_scan_data.get("product", {}) if raw_scan_data else {}
        product_name = product_info.get("name") or (raw_scan_data.get("scan_code") if raw_scan_data else None)
        brand = product_info.get("brand") or ""
        scan_status = raw_scan_data.get("status") if raw_scan_data else None
        declarations = raw_scan_data.get("declarations", []) if raw_scan_data else []
        quality_metrics = raw_scan_data.get("quality_metrics", []) if raw_scan_data else []

        # Find specific declarations from active session
        mrp_decls = [d for d in declarations if "MRP" in (d.get("declaration_type") or "")]
        qty_decls = [d for d in declarations if "QUANTITY" in (d.get("declaration_type") or "")]
        mfg_decls = [d for d in declarations if any(k in (d.get("declaration_type") or "") for k in ["MANUFACTURER", "PACKER", "IMPORTER"])]
        care_decls = [d for d in declarations if "CONSUMER_CARE" in (d.get("declaration_type") or "")]
        date_decls = [d for d in declarations if any(k in (d.get("declaration_type") or "") for k in ["DATE", "EXPIRY", "BEFORE"])]

        # 1. Greeting & Social Intents
        if intent == IntentType.GREETING_OR_CHITCHAT:
            if product_name:
                response_text = (
                    f"Hello! 👋 I am your **LegalMetrix AI Regulatory Copilot**.\n\n"
                    f"I see you are currently inspecting **{product_name}**"
                    f"{f' ({brand})' if brand else ''}.\n\n"
                    f"You can ask me to:\n"
                    f"- **Check MRP Compliance**: Verify currency symbols and tax clauses.\n"
                    f"- **Verify Net Quantity**: Validate metric units (`g`, `kg`, `ml`).\n"
                    f"- **Review Consumer Care**: Check helpline phone, email, and address.\n"
                    f"- **Explain Diagnostics**: Get tips for photo glare or blur warnings.\n\n"
                    f"How can I assist your inspection session today?"
                )
            else:
                response_text = (
                    "Hello! 👋 I am your **LegalMetrix AI Regulatory Copilot**.\n\n"
                    "I am here to assist you with package declaration compliance under the **Legal Metrology (Packaged Commodities) Rules, 2011**.\n\n"
                    "You can upload package photos, ask regulatory questions, or inspect active scan sessions. How can I help you today?"
                )

        # 2. Politeness / Gratitude Intents
        elif intent == IntentType.POLITENESS_OR_THANKS:
            response_text = (
                "You're very welcome! Feel free to ask if you need any further assistance with your package inspection, OCR verification, or Legal Metrology rules."
            )

        # 3. System Navigation / Capabilities
        elif intent == IntentType.SYSTEM_NAVIGATION_HELP:
            response_text = (
                "**I am the LegalMetrix AI Assistant**, your specialized regulatory co-pilot for packaged commodity inspection.\n\n"
                "**What I Can Do:**\n"
                "1. **Legal Metrology Checks**: Verify mandatory label declarations under Rule 6 of LMR 2011 (MRP, Net Quantity, Dates, Manufacturer Address, Consumer Care, Country of Origin).\n"
                "2. **Image Quality Advice**: Explain blur, glare, and resolution diagnostics, offering practical camera capture tips.\n"
                "3. **Evidence Verification**: Help you interpret OCR text polygons and navigate human-in-the-loop declaration review.\n"
                "4. **Audit & Reporting**: Guide you on compliance findings and official inspection notice drafting."
            )

        # 4. Specific Declaration Check
        elif intent == IntentType.SPECIFIC_DECLARATION_CHECK:
            if "mrp" in target_fields:
                if mrp_decls:
                    top_mrp = mrp_decls[0]
                    raw = top_mrp.get("raw_text", "")
                    conf = top_mrp.get("confidence", 0.0)
                    status = top_mrp.get("review_status", "UNREVIEWED")
                    response_text = (
                        f"**MRP Declaration Analysis" + (f" for {product_name}:**\n\n" if product_name else ":**\n\n") +
                        f"- **Extracted Text**: `{raw}`\n"
                        f"- **Confidence Score**: `{conf:.2f}`\n"
                        f"- **Current Review Status**: `{status}`\n\n"
                        f"**Regulatory Checklist (Rule 6(1)(e)):**\n"
                        f"1. **Currency**: Must use standard currency indicator (`Rs.` or `₹`).\n"
                        f"2. **Tax Clause**: Must include mandatory text `inclusive of all taxes` or `incl. of all taxes`.\n"
                        f"3. **Unit Sale Price (USP)**: For packages > 1kg or > 1L, declaring unit price (e.g. `₹ per g / ml`) is mandatory.\n\n"
                        f"👉 **Action**: If accurate, mark the MRP declaration card as **Confirmed** in the Inspection Workspace."
                    )
                else:
                    response_text = (
                        f"**MRP Compliance Requirements (Rule 6(1)(e)):**\n\n"
                        f"Under the Legal Metrology Rules, the retail sale price must be clearly printed in the format:\n"
                        f"- `MRP Rs. XX.XX (incl. of all taxes)` or `₹ XX.XX (inclusive of all taxes)`.\n\n"
                        + (f"*(Note: No distinct MRP declaration has been extracted yet for **{product_name}**. Please check if the price is printed on another panel or obscured by lighting).*" if product_name else "")
                    )
            elif "net_quantity" in target_fields:
                if qty_decls:
                    top_qty = qty_decls[0]
                    raw = top_qty.get("raw_text", "")
                    conf = top_qty.get("confidence", 0.0)
                    response_text = (
                        f"**Net Quantity Declaration Analysis" + (f" for {product_name}:**\n\n" if product_name else ":**\n\n") +
                        f"- **Extracted Text**: `{raw}`\n"
                        f"- **Confidence**: `{conf:.2f}`\n\n"
                        f"**Rule 6(1)(b) Standards:**\n"
                        f"- Must be declared in standard metric units: `g`, `kg` for mass; `ml`, `l` for liquids; or `N / units` for count.\n"
                        f"- Symbols must be lowercase (`g`, `kg`, `ml`) without periods or plurals (e.g. `gms` or `kgs` is non-compliant).\n\n"
                        f"👉 Verify this value against the Principal Display Panel (PDP) and confirm in your review queue."
                    )
                else:
                    response_text = (
                        "**Net Quantity Declaration Standards (Rule 6(1)(b)):**\n\n"
                        "- Must be declared in standard metric units (`g`, `kg`, `ml`, `l`, `m`, `N`).\n"
                        "- Non-standard imperial units (e.g. *oz*, *lbs*) cannot be used alone.\n"
                        "- Minimum font height is governed by total net quantity (e.g. minimum 2mm to 6mm height)."
                    )
            elif "consumer_care" in target_fields:
                response_text = (
                    f"**Consumer Care Redressal Declaration (Rule 6(1)(h)):**\n\n"
                    f"Every packaged commodity must provide a complete grievance redressal mechanism containing:\n"
                    f"1. **Contact Person / Officer**: Designated consumer care officer name or office.\n"
                    f"2. **Helpline Number**: Dedicated toll-free or customer care telephone number (e.g. `1800-XX-XXXX`).\n"
                    f"3. **Email ID**: Active consumer feedback email (e.g. `care@company.com`).\n"
                    f"4. **Postal Address**: Complete physical address for grievance correspondence.\n\n"
                    + (f"In **{product_name}**, verify whether both telephone and email contact details are clearly legible." if product_name else "")
                )
            elif "manufacturer" in target_fields:
                if mfg_decls:
                    raw_mfg = mfg_decls[0].get("raw_text", "")
                    response_text = (
                        f"**Manufacturer / Packer Declaration (Rule 6(1)(a)):**\n\n"
                        f"- **Extracted Address**: `{raw_mfg}`\n\n"
                        f"**Requirements:**\n"
                        f"- Complete registered address with city, state, and pin code.\n"
                        f"- If manufactured by one company and packed/marketed by another, both entities must be clearly identified."
                    )
                else:
                    response_text = (
                        "**Manufacturer Details Standards (Rule 6(1)(a)):**\n\n"
                        "The package must display the full name and postal address of the manufacturer or packer (or importer for imported items)."
                    )
            else:
                response_text = (
                    f"**Declaration Evaluation:**\n\n"
                    f"Under Rule 6 of the Legal Metrology (Packaged Commodities) Rules, 2011, all declarations must be clear, un-obscured, and in standard formats."
                )

        # 5. Image Quality & Diagnostics Inquiries
        elif intent == IntentType.IMAGE_QUALITY_DIAGNOSTIC:
            response_text = (
                "**LegalMetrix AI Image Quality Diagnostics:**\n\n"
                "- **Sharpness / Blur (Laplacian Variance)**:\n"
                "  • Score $\\ge 100.0$: `ACCEPTED`\n"
                "  • Score $< 40.0$: `RECAPTURE_RECOMMENDED` (defocus / motion blur)\n\n"
                "- **Specular Glare (Highlight Ratio)**:\n"
                "  • Threshold: $\\le 5.0\\%$ of package area\n"
                "  • Severe Glare: $> 17.5\\%$ triggers `RECAPTURE_RECOMMENDED`\n\n"
                "**💡 Inspector Tip for Shiny / Plastic Packaging:**\n"
                "Tilt the camera at a $15^\\circ - 25^\\circ$ angle rather than pointing directly perpendicular to overhead lighting to eliminate specular flare."
            )

        # 6. Legal Regulation Inquiry
        elif intent == IntentType.LEGAL_REGULATION_INQUIRY:
            response_text = (
                "**Legal Metrology (Packaged Commodities) Rules, 2011 — Regulatory Framework:**\n\n"
                "Under **Rule 6**, every retail packaged commodity must declare:\n"
                "1. **Name & Address** of Manufacturer / Packer / Importer (Rule 6(1)(a))\n"
                "2. **Net Quantity** in standard metric units with minimum font sizes (Rule 6(1)(b))\n"
                "3. **Dates** of manufacture/packaging and expiry (Rule 6(1)(c)/(d))\n"
                "4. **Maximum Retail Price (MRP)** inclusive of all taxes (Rule 6(1)(e))\n"
                "5. **Consumer Care** grievance redressal contact (Rule 6(1)(h))\n"
                "6. **Country of Origin** for imported goods (Rule 6(1)(n))\n\n"
                "Non-compliance may attract statutory penalties under Section 36 of the Legal Metrology Act, 2009."
            )

        # 7. Product Overview / Summary
        elif intent == IntentType.PRODUCT_COMPLIANCE_OVERVIEW:
            if product_name:
                total_decls = len(declarations)
                response_text = (
                    f"**Inspection Overview for {product_name}**" + (f" (Brand: {brand})" if brand else "") + f":\n\n"
                    f"- **Session Status**: `{scan_status or 'PROCESSING'}`\n"
                    f"- **Extracted Declarations**: Found `{total_decls}` candidate declaration(s).\n\n"
                    f"**Key Mandatory Declarations Detected:**\n"
                    f"- **MRP**: {('`' + mrp_decls[0].get('raw_text', '') + '`') if mrp_decls else '⚠️ *Needs review / Not yet isolated*'}\n"
                    f"- **Net Quantity**: {('`' + qty_decls[0].get('raw_text', '') + '`') if qty_decls else '⚠️ *Needs review*'}\n"
                    f"- **Manufacturer / Packer**: {('`' + mfg_decls[0].get('raw_text', '')[:60] + '...`') if mfg_decls else '⚠️ *Needs verification*'}\n"
                    f"- **Consumer Care**: {('`' + care_decls[0].get('raw_text', '')[:60] + '...`') if care_decls else '⚠️ *Needs verification*'}\n\n"
                    f"👉 **Next Step**: Click on the declaration cards in the Inspection Workspace to verify against highlighted OCR bounding boxes, then mark them as **Confirmed** or **Corrected**."
                )
            else:
                response_text = (
                    "**LegalMetrix AI Inspection Workflow:**\n\n"
                    "1. **Capture & Upload**: Upload multi-panel package images (`FRONT`, `BACK`, `SIDES`).\n"
                    "2. **Diagnostics & OCR**: OpenCV evaluates sharpness/glare and PaddleOCR extracts text blocks.\n"
                    "3. **Declaration Review**: Review candidate cards, verify bounding boxes, and confirm/edit.\n"
                    "4. **Rule Engine**: Evaluates compliance against LMR 2011 to issue `PASS`, `FAIL`, or `REVIEW`.\n"
                    "5. **Reports**: Download official audit dossiers and PDF compliance notices."
                )

        # 8. General Fallback
        else:
            response_text = (
                f"**Legal Metrology Regulatory Guidance:**\n\n"
                f"Under the **Legal Metrology (Packaged Commodities) Rules, 2011 (Rule 6)**, all pre-packaged commodities sold in India must display mandatory declarations:\n\n"
                f"1. **Manufacturer / Packer Name & Postal Address** (Rule 6(1)(a))\n"
                f"2. **Net Quantity in Standard Metric Units** (Rule 6(1)(b))\n"
                f"3. **Dates of Manufacture / Packing** (Rule 6(1)(c)/(d))\n"
                f"4. **Maximum Retail Price (MRP)** inclusive of all taxes (Rule 6(1)(e))\n"
                f"5. **Consumer Care Grievance Redressal Contact** (Rule 6(1)(h))\n"
                f"6. **Country of Origin** for imported commodities (Rule 6(1)(n))\n\n"
                f"Please let me know if you would like me to evaluate any specific declaration or explain a particular rule in detail."
            )

        # Typewriter SSE streaming output
        words = response_text.split(" ")
        for i, word in enumerate(words):
            chunk_str = word + (" " if i < len(words) - 1 else "")
            sse_payload = json.dumps({
                "text": chunk_str,
                "done": False,
                "tokens_saved": tokens_saved,
                "intent": intent.value,
            })
            yield f"data: {sse_payload}\n\n"
            await asyncio.sleep(0.015)  # 15ms pacing

        yield f"data: {json.dumps({'text': '', 'done': True, 'tokens_saved': tokens_saved, 'intent': intent.value})}\n\n"


_assistant_service_instance: Optional[AssistantService] = None


def get_assistant_service() -> AssistantService:
    global _assistant_service_instance
    if _assistant_service_instance is None:
        _assistant_service_instance = AssistantService()
    return _assistant_service_instance
