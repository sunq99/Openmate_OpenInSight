# OpenInSight Chatbot

지역 분석 데이터 기반 LLM 챗봇 구현 코드입니다.
Google Gemini + LangChain을 활용하여 가맹점·매출 데이터를 자연어로 질의응답합니다.

## 기술 스택

- **Backend**: FastAPI, LangChain, Google Gemini
- **Frontend**: React, Zustand
- **통신 방식**: SSE(Server-Sent Events) 스트리밍

## 구조

```
backend/app/
├── routers/chat.py        # API 엔드포인트 (send / stream / feedback / clear)
├── schemas/chat.py        # 요청·응답 Pydantic 스키마
└── services/
    ├── chat_service.py    # LLM 연동, 스트리밍, 대화 이력 관리
    └── prompts.py         # 인텐트별 프롬프트 템플릿

frontend/src/
├── components/chatbot/
│   ├── ChatBotMessage.jsx         # 메시지 말풍선 컴포넌트
│   └── ChatBotTypingIndicator.jsx # 타이핑 애니메이션
├── api/chatApi.ts                 # SSE 스트리밍 API 호출 레이어
├── pages/user/ChatBotPage.jsx     # 챗봇 메인 페이지
└── store/chatStore.js             # Zustand 대화 상태 관리
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/chat/send` | 일반 응답 (단건) |
| POST | `/api/chat/stream` | SSE 스트리밍 응답 |
| DELETE | `/api/chat/conversation/{id}` | 대화 이력 초기화 |
| POST | `/api/chat/feedback` | 답변 평가 저장 (👍/👎) |

## 주요 기능

- **SSE 스트리밍**: 토큰 단위 실시간 응답 (ThreadPoolExecutor 기반)
- **대화 이력 관리**: 인메모리 저장, TTL 30분 자동 만료
- **인텐트 분류**: 축제 목록, 매출 분석 등 질문 유형에 따라 맞춤 응답
- **축제 컨텍스트 유지**: 대화 중 선택된 축제 정보를 세션 동안 추적
- **차트 데이터 자동 생성**: 응답에 Bar, Line, Doughnut 차트 데이터 포함
- **피드백 저장**: 사용자 평가(좋아요/싫어요)를 DB에 기록

## 환경 변수

```env
CHAT_CONV_TTL_SECONDS=1800    # 대화 이력 유지 시간 (기본 30분)
CHAT_CLEANUP_INTERVAL=300     # 만료 이력 정리 주기 (기본 5분)
CHAT_LLM_TIMEOUT=120          # LLM 응답 타임아웃 (기본 2분)
```
