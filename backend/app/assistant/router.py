"""
LegalMetrix AI Assistant — FastAPI Router with Dynamic Intent-Driven SSE Streaming Endpoints
"""

import json
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.assistant.context_optimizer import ContextOptimizer
from app.assistant.intent_classifier import IntentClassificationResult, IntentClassifier
from app.assistant.schemas import (
    AssistantStatusResponse,
    ChatMessage,
    ChatResponse,
    ChatStreamRequest,
)
from app.assistant.service import AssistantService, get_assistant_service
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.declaration import Declaration
from app.models.image_quality import ImageQualityMetric
from app.models.scan_session import ScanSession
from app.models.user import User

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


def _gather_scan_context(
    db: Session,
    scan_id: Optional[str],
    user_query: str,
    history: Optional[List[ChatMessage]] = None,
) -> Tuple[str, Optional[dict], int, IntentClassificationResult]:
    """Retrieves and optimizes scan evidence context with intent-driven semantic filtering."""
    active_product_name = None
    scan_data = None
    quality_metrics = []
    declarations = []

    if scan_id:
        scan = db.query(ScanSession).filter(ScanSession.id == scan_id).first()
        if scan:
            active_product_name = scan.product.name if scan.product else scan.scan_code
            scan_data = {
                "id": scan.id,
                "scan_code": scan.scan_code,
                "status": scan.status,
                "product": {
                    "name": scan.product.name if scan.product else None,
                    "brand": scan.product.brand if scan.product else None,
                    "barcode": scan.product.barcode if scan.product else None,
                } if scan.product else None,
            }

            if scan.images:
                image_ids = [img.id for img in scan.images]
                metrics = db.query(ImageQualityMetric).filter(ImageQualityMetric.scan_image_id.in_(image_ids)).all()
                for m in metrics:
                    quality_metrics.append({
                        "quality_status": m.quality_status,
                        "blur_score": m.blur_score,
                        "glare_score": m.glare_score,
                        "warnings": m.warnings or [],
                    })

            decls = db.query(Declaration).filter(Declaration.scan_session_id == scan.id).all()
            for d in decls:
                declarations.append({
                    "declaration_type": d.declaration_type,
                    "raw_text": d.raw_text,
                    "confidence": d.confidence,
                    "review_status": d.review_status,
                })

    # 1. Classify Intent & Rewrite Query
    intent_result = IntentClassifier.classify(
        message=user_query,
        history=history or [],
        active_product_name=active_product_name,
    )

    # 2. Optimize and chunk context string based on intent
    filtered_context, tokens_saved = ContextOptimizer.filter_scan_context(
        user_query=user_query,
        scan_data=scan_data,
        quality_metrics=quality_metrics,
        declarations=declarations,
        findings=[],
        intent_result=intent_result,
    )

    raw_scan_data = None
    if scan_data:
        raw_scan_data = {
            "id": scan_data["id"],
            "scan_code": scan_data["scan_code"],
            "status": scan_data["status"],
            "product": scan_data.get("product"),
            "declarations": declarations,
            "quality_metrics": quality_metrics,
        }

    return filtered_context, raw_scan_data, tokens_saved, intent_result


@router.post("/stream")
async def stream_assistant_chat(
    payload: ChatStreamRequest,
    db: Session = Depends(get_db),
    assistant_service: AssistantService = Depends(get_assistant_service),
):
    """
    Real-time Server-Sent Events (SSE) streaming endpoint for AI Assistant.
    Supports voice transcripts, multimodal image payloads, dynamic intent routing, and token-saving chunking.
    """
    scan_context, raw_scan_data, tokens_saved, intent_result = _gather_scan_context(
        db, payload.scan_id, payload.message, payload.history
    )

    return StreamingResponse(
        assistant_service.stream_chat(
            payload,
            scan_context_str=scan_context,
            raw_scan_data=raw_scan_data,
            tokens_saved=tokens_saved,
            intent_result=intent_result,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    payload: ChatStreamRequest,
    db: Session = Depends(get_db),
    assistant_service: AssistantService = Depends(get_assistant_service),
):
    """
    Non-streaming synchronous chat endpoint for standard REST clients with intent metadata.
    """
    scan_context, raw_scan_data, tokens_saved, intent_result = _gather_scan_context(
        db, payload.scan_id, payload.message, payload.history
    )
    full_text = ""

    async for chunk in assistant_service.stream_chat(
        payload,
        scan_context_str=scan_context,
        raw_scan_data=raw_scan_data,
        tokens_saved=tokens_saved,
        intent_result=intent_result,
    ):
        if chunk.startswith("data: "):
            try:
                data = json.loads(chunk[6:].strip())
                full_text += data.get("text", "")
            except Exception:
                pass

    return ChatResponse(
        reply=full_text,
        suggested_actions=["Verify MRP declaration", "Check image quality", "Explain Rule 6 requirements"],
        citations=["LMR 2011 Rule 6(1)(e)", "LMR 2011 Rule 6(1)(b)"],
        tokens_saved_estimate=tokens_saved,
        detected_intent=intent_result.intent.value,
        target_fields=intent_result.target_fields,
    )


@router.get("/status", response_model=AssistantStatusResponse)
def get_assistant_status(
    assistant_service: AssistantService = Depends(get_assistant_service),
):
    """Returns AI Assistant engine operational status and capabilities."""
    active_provider = assistant_service._determine_active_provider()
    return AssistantStatusResponse(
        status="operational",
        provider=active_provider,
        model=assistant_service.model or "default",
        streaming_supported=True,
        multimodal_supported=True,
        voice_support=True,
        context_chunking=True,
        intent_routing=True,
    )
