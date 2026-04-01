"""챗봇 라우터"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse, ChatFeedbackRequest
from app.schemas.common import MessageResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["챗봇"])


@router.post("/send", response_model=ChatResponse)
async def send_message(
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """챗봇 메시지 전송 및 응답"""
    service = ChatService()
    return await service.process_message(
        user_id=current_user["user_id"],
        message=req.message,
        conversation_id=req.conversation_id,
    )


@router.post("/stream")
async def stream_message(
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """챗봇 메시지 스트리밍 응답 (SSE)"""
    service = ChatService()
    return StreamingResponse(
        service.stream_message(
            user_id=current_user["user_id"],
            message=req.message,
            conversation_id=req.conversation_id,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/conversation/{conversation_id}", response_model=MessageResponse)
async def clear_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    """대화 이력 삭제 (인메모리)"""
    service = ChatService()
    service.clear_conversation(conversation_id)
    return MessageResponse(message="대화가 초기화되었습니다.")


@router.post("/feedback", response_model=MessageResponse)
async def submit_feedback(
    req: ChatFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """챗봇 답변 평가 저장 (👍=1, 👎=-1)"""
    service = ChatService()
    await service.save_feedback(db, req)
    return MessageResponse(message="평가가 저장되었습니다.")
