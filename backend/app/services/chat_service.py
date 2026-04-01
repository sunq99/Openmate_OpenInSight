"""챗봇 서비스 — ImprovedTextToSQL 연동"""

import asyncio
import concurrent.futures
import json
import os
import threading
import time
import uuid
from typing import Any, AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.schemas.chat import ChatResponse, ChatFeedbackRequest
from app.services.llm_instance import get_chatbot

# 스트리밍용 공유 스레드풀 — 요청마다 새로 생성하지 않고 재사용
_stream_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="chat_stream",
)

# conversation_id → {"data": [...], "last_accessed": float}
_conversation_histories: dict[str, dict] = {}
# conversation_id → {"data": {...}, "last_accessed": float}
_conversation_festival_ctx: dict[str, dict] = {}

_CONV_TTL_SECONDS = int(os.getenv("CHAT_CONV_TTL_SECONDS", "1800"))      # 기본 30분
_CLEANUP_INTERVAL = int(os.getenv("CHAT_CLEANUP_INTERVAL", "300"))       # 기본 5분
_LLM_TIMEOUT = int(os.getenv("CHAT_LLM_TIMEOUT", "120"))                 # LLM 응답 타임아웃 (기본 2분)

# 축제 교체 감지 키워드 — 한 곳에서만 관리
_OTHER_FESTIVAL_KEYWORDS = ['다른 축제', '다른축제', '다른 행사', '다른 보고서', '다른 데이터']


def _histories_get(conversation_id: str) -> list[dict]:
    entry = _conversation_histories.get(conversation_id)
    if entry:
        entry["last_accessed"] = time.time()
        return entry["data"]
    return []


def _histories_set(conversation_id: str, data: list[dict]) -> None:
    _conversation_histories[conversation_id] = {"data": data, "last_accessed": time.time()}


def _festival_ctx_get(conversation_id: str) -> dict | None:
    entry = _conversation_festival_ctx.get(conversation_id)
    if entry:
        entry["last_accessed"] = time.time()
        return entry["data"]
    return None


def _festival_ctx_set(conversation_id: str, data: dict) -> None:
    _conversation_festival_ctx[conversation_id] = {"data": data, "last_accessed": time.time()}


async def _cleanup_stale_conversations() -> None:
    """만료된 대화 이력을 주기적으로 삭제"""
    logger.info(f"대화 이력 TTL 정리 태스크 시작 (TTL={_CONV_TTL_SECONDS}s, 주기={_CLEANUP_INTERVAL}s)")
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL)
        cutoff = time.time() - _CONV_TTL_SECONDS
        expired = [
            cid for cid, entry in list(_conversation_histories.items())
            if entry["last_accessed"] < cutoff
        ]
        for cid in expired:
            _conversation_histories.pop(cid, None)
            _conversation_festival_ctx.pop(cid, None)
        if expired:
            logger.info(f"대화 이력 TTL 정리: {len(expired)}개 삭제")


class ChatService:
    async def process_message(
        self,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
    ) -> ChatResponse:
        """메시지 처리 — LLM 쿼리 실행 및 응답 반환"""
        if not conversation_id:
            conversation_id = uuid.uuid4().hex

        logger.info(f"Chat message from {user_id} [conv={conversation_id}]: {message[:80]}")

        chatbot = get_chatbot()
        history = _histories_get(conversation_id)
        prev_festival_ctx = _festival_ctx_get(conversation_id)

        loop = asyncio.get_event_loop()
        try:
            result: dict[str, Any] | None = await asyncio.wait_for(
                loop.run_in_executor(
                    None, lambda: chatbot.query(
                        message,
                        user_id=user_id,
                        conversation_history=history,
                        previous_festival_context=prev_festival_ctx,
                    )
                ),
                timeout=_LLM_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(f"LLM 응답 타임아웃 ({_LLM_TIMEOUT}s) [conv={conversation_id}]")
            return ChatResponse(
                reply="응답 생성 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
                conversation_id=conversation_id,
            )

        if result is None:
            return ChatResponse(
                reply="죄송합니다. 응답을 생성하지 못했습니다. 다시 시도해 주세요.",
                conversation_id=conversation_id,
            )

        _histories_set(conversation_id, result.get("conversation_history", history))

        # 축제 컨텍스트 업데이트:
        # - 처음 확정된 경우 저장
        # - "다른 축제" 질문으로 새 축제가 선택된 경우 교체
        # - 축제_목록 결과도 저장(후속 랭킹 질문에서 재사용하기 위해)
        is_other_festival_query = any(kw in message for kw in _OTHER_FESTIVAL_KEYWORDS)
        is_festival_list_result = result.get("intent") == "축제_목록"
        new_ctx = result.get("festival_context")
        if new_ctx and (not prev_festival_ctx or is_other_festival_query or is_festival_list_result):
            _festival_ctx_set(conversation_id, new_ctx)

        return ChatResponse(
            reply=result.get("answer", ""),
            conversation_id=conversation_id,
            chart_type=result.get("chart_type"),
            chart_data=result.get("chart_data"),
            suggested_question=result.get("suggested_question"),
        )

    async def stream_message(
        self,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """SSE 스트리밍 응답 — STEP 4 토큰을 실시간으로 yield"""
        if not conversation_id:
            conversation_id = uuid.uuid4().hex

        logger.info(f"Stream message from {user_id} [conv={conversation_id}]: {message[:80]}")

        chatbot = get_chatbot()
        history = _histories_get(conversation_id)
        prev_festival_ctx = _festival_ctx_get(conversation_id)

        loop = asyncio.get_event_loop()
        q: asyncio.Queue = asyncio.Queue()

        stop_event = threading.Event()

        def _run_generator():
            try:
                for item in chatbot.query_stream(message, user_id, history, prev_festival_ctx):
                    if stop_event.is_set():
                        break
                    loop.call_soon_threadsafe(q.put_nowait, item)
            except Exception as exc:
                logger.exception("stream_message: generator 오류")
                loop.call_soon_threadsafe(q.put_nowait, {"type": "error", "message": str(exc)})
            finally:
                loop.call_soon_threadsafe(q.put_nowait, None)  # sentinel

        loop.run_in_executor(_stream_executor, _run_generator)

        is_other_festival_query = any(kw in message for kw in _OTHER_FESTIVAL_KEYWORDS)

        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=_LLM_TIMEOUT)
                except asyncio.TimeoutError:
                    logger.warning(f"스트리밍 응답 타임아웃 ({_LLM_TIMEOUT}s) [conv={conversation_id}]")
                    yield f"data: {json.dumps({'type': 'error', 'message': '응답 생성 시간이 초과되었습니다.'}, ensure_ascii=False)}\n\n"
                    stop_event.set()
                    break

                if item is None:
                    break

                if item["type"] == "metadata":
                    # 내부 상태 추출 및 저장
                    conv_history = item.pop("_conversation_history", None)
                    festival_ctx = item.pop("_festival_ctx", None)
                    intent = item.pop("_intent", None)

                    if conv_history is not None:
                        _histories_set(conversation_id, conv_history)

                    is_festival_list_result = intent == "축제_목록"
                    if festival_ctx and (not prev_festival_ctx or is_other_festival_query or is_festival_list_result):
                        _festival_ctx_set(conversation_id, festival_ctx)

                    # 클라이언트에 conversation_id, intent 포함해서 전송
                    item["conversation_id"] = conversation_id
                    if intent is not None:
                        item["_intent"] = intent

                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        except (GeneratorExit, asyncio.CancelledError):
            logger.info(f"Client disconnected [conv={conversation_id}]")
            stop_event.set()

    def clear_conversation(self, conversation_id: str) -> None:
        """대화 삭제 (인메모리)"""
        _conversation_histories.pop(conversation_id, None)
        _conversation_festival_ctx.pop(conversation_id, None)

    @staticmethod
    def conversation_count() -> int:
        """현재 인메모리에 보관 중인 대화 수 (모니터링용)"""
        return len(_conversation_histories)

    async def save_feedback(self, db: AsyncSession, req: ChatFeedbackRequest) -> None:
        """챗봇 답변 평가 저장"""
        await db.execute(
            text(
                "INSERT INTO openinsight_prod.tb_chat_feedback "
                "(rating, question, answer) VALUES (:rating, :question, :answer)"
            ),
            {"rating": req.rating, "question": req.question, "answer": req.answer},
        )
        await db.commit()
        logger.info(f"Chat feedback saved: rating={req.rating}")
