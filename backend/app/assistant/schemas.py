from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message text content")
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    image_base64: Optional[str] = Field(None, description="Optional Base64 encoded image for multimodal query")
    image_mime_type: Optional[str] = Field(None, description="MIME type of the attached image (e.g. image/jpeg)")


class ChatStreamRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User prompt or speech-to-text transcript")
    history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Recent conversation turns (last 3-4 messages)")
    scan_id: Optional[str] = Field(None, description="Active inspection session ID for contextual grounding")
    image_base64: Optional[str] = Field(None, description="Optional image base64 data for visual reasoning")
    image_mime_type: Optional[str] = Field(default="image/jpeg", description="MIME type of base64 image")
    user_role: Optional[str] = Field(default="INSPECTOR", description="Current user role (INSPECTOR, REVIEWER, ADMIN)")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Full text reply from assistant")
    suggested_actions: Optional[List[str]] = Field(default_factory=list, description="Context-aware quick follow-ups")
    citations: Optional[List[str]] = Field(default_factory=list, description="Relevant LMR 2011 rule citations")
    tokens_saved_estimate: Optional[int] = Field(0, description="Estimated tokens saved by chunking & context optimizer")
    detected_intent: Optional[str] = Field(None, description="Classified intent tag")
    target_fields: Optional[List[str]] = Field(default_factory=list, description="Target declaration entities extracted")


class AssistantStatusResponse(BaseModel):
    status: str = "operational"
    provider: str
    model: str
    streaming_supported: bool = True
    multimodal_supported: bool = True
    voice_support: bool = True
    context_chunking: bool = True
    intent_routing: bool = True

