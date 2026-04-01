"""챗봇 스키마"""

from typing import Optional, Literal

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """챗봇 메시지 요청"""

    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    """챗봇 응답"""

    reply: str
    conversation_id: str
    chart_type: Optional[str] = None
    chart_data: Optional[dict] = None
    suggested_question: Optional[str] = None


class ChatFeedbackRequest(BaseModel):
    """챗봇 답변 평가 요청"""

    rating: Literal[1, -1]
    question: str
    answer: str
