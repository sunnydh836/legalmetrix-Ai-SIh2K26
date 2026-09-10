"""
Tests for AI Assistant Intent Classifier, Modular Prompting, Dynamic Context Routing, and Streaming SSE.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.assistant.context_optimizer import ContextOptimizer
from app.assistant.intent_classifier import IntentClassifier, IntentType
from app.assistant.prompts import compose_adaptive_system_prompt
from app.assistant.schemas import ChatMessage


def test_intent_classifier_greetings():
    res = IntentClassifier.classify("Hello there!", history=[])
    assert res.intent == IntentType.GREETING_OR_CHITCHAT
    assert res.target_fields == []
    assert res.requires_legal_rules is False


def test_intent_classifier_declaration_checks():
    # MRP Check
    res_mrp = IntentClassifier.classify("What is the MRP printed on the box?", history=[])
    assert res_mrp.intent == IntentType.SPECIFIC_DECLARATION_CHECK
    assert "mrp" in res_mrp.target_fields

    # Net quantity check
    res_qty = IntentClassifier.classify("Check if the net weight in grams is valid", history=[])
    assert res_qty.intent == IntentType.SPECIFIC_DECLARATION_CHECK
    assert "net_quantity" in res_qty.target_fields

    # Consumer care check
    res_care = IntentClassifier.classify("Is the customer care helpline and email present?", history=[])
    assert res_care.intent == IntentType.SPECIFIC_DECLARATION_CHECK
    assert "consumer_care" in res_care.target_fields


def test_intent_classifier_image_quality_with_panel():
    res = IntentClassifier.classify("The back photo is blurry and has too much glare", history=[])
    assert res.intent == IntentType.IMAGE_QUALITY_DIAGNOSTIC
    assert res.panel_referenced == "BACK"
    assert res.requires_scan_data is True


def test_intent_classifier_legal_inquiry():
    res = IntentClassifier.classify("What are the mandatory provisions under Rule 6 of LMR 2011?", history=[])
    assert res.intent == IntentType.LEGAL_REGULATION_INQUIRY
    assert res.requires_legal_rules is True


def test_intent_classifier_query_rewriting():
    res = IntentClassifier.classify(
        message="What is the price of it?",
        history=[ChatMessage(role="user", content="Checking Scan 101")],
        active_product_name="Fortune Sunlite Oil 1L",
    )
    assert res.intent == IntentType.SPECIFIC_DECLARATION_CHECK
    assert "Fortune Sunlite Oil 1L" in res.rewritten_query
    assert "mrp" in res.target_fields


def test_modular_prompt_composition():
    prompt = compose_adaptive_system_prompt(
        intent=IntentType.SPECIFIC_DECLARATION_CHECK,
        user_role="INSPECTOR",
        scan_context_str="MRP: Rs. 150",
    )
    assert "LegalMetrix AI Assistant" in prompt
    assert "Field Inspector" in prompt
    assert "MRP: Rs. 150" in prompt
    assert "Rule 6" in prompt


@pytest.mark.asyncio
async def test_assistant_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/assistant/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert data["streaming_supported"] is True
        assert data["voice_support"] is True
        assert data["context_chunking"] is True
        assert data["intent_routing"] is True


@pytest.mark.asyncio
async def test_assistant_stream_sse():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "message": "What is the mandatory MRP declaration under Rule 6?",
            "history": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hello Inspector!"}
            ],
            "user_role": "INSPECTOR"
        }
        response = await ac.post("/api/v1/assistant/stream", json=payload)
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        content = response.text
        assert "data: " in content
        assert "MRP" in content


@pytest.mark.asyncio
async def test_assistant_chat_sync():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "message": "Explain glare warning threshold",
            "history": [],
            "user_role": "INSPECTOR"
        }
        response = await ac.post("/api/v1/assistant/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert len(data["reply"]) > 0
        assert data["detected_intent"] == "IMAGE_QUALITY_DIAGNOSTIC"


def test_context_optimizer_pruning():
    history = [
        ChatMessage(role="user", content=f"Message {i}")
        for i in range(10)
    ]
    pruned = ContextOptimizer.prune_history(history)
    # Should keep only max turns (8 messages max)
    assert len(pruned) <= 8
    assert pruned[-1]["content"] == "Message 9"


def test_context_optimizer_filtering():
    scan_data = {
        "id": "SCAN-001",
        "product": {"name": "Test Atta", "brand": "BrandX"},
        "status": "COMPLETED"
    }
    decls = [
        {"declaration_type": "MRP", "raw_text": "MRP Rs. 100", "confidence": 0.95},
        {"declaration_type": "NET_QUANTITY", "raw_text": "1 kg", "confidence": 0.90},
        {"declaration_type": "MANUFACTURER", "raw_text": "ABC Ltd", "confidence": 0.85},
    ]

    # Query specifically about MRP
    context, tokens_saved = ContextOptimizer.filter_scan_context(
        user_query="What is the MRP?",
        scan_data=scan_data,
        quality_metrics=[],
        declarations=decls,
        findings=[]
    )
    assert "MRP" in context
    assert "BrandX" in context
    # NET_QUANTITY and MANUFACTURER should be excluded from targeted context
    assert "NET_QUANTITY" not in context
    assert "ABC Ltd" not in context


@pytest.mark.asyncio
async def test_assistant_greeting_intent():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "message": "Hi good morning",
            "history": [],
            "user_role": "INSPECTOR"
        }
        response = await ac.post("/api/v1/assistant/chat", json=payload)
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "Hello!" in reply or "LegalMetrix AI" in reply
        # Ensure no raw bracketed headers are leaked
        assert "[Active Scan:" not in reply
        assert "Current Scan Context Loaded:" not in reply
        assert response.json()["detected_intent"] == "GREETING_OR_CHITCHAT"


@pytest.mark.asyncio
async def test_assistant_thanks_intent():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "message": "thanks",
            "history": [],
            "user_role": "INSPECTOR"
        }
        response = await ac.post("/api/v1/assistant/chat", json=payload)
        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "welcome" in reply.lower()
        assert response.json()["detected_intent"] == "POLITENESS_OR_THANKS"
