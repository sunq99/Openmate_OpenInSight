# OpenInSight Chatbot

LLM 기반 지역 분석 챗봇 구현 코드입니다.

## 기술 스택

- **Backend**: FastAPI, LangChain, Google Gemini
- **Frontend**: React, Zustand

## 구조

```
backend/app/
├── routers/chat.py        # SSE 스트리밍 엔드포인트
├── schemas/chat.py        # 요청/응답 스키마
└── services/
    ├── chat_service.py    # LLM 연동 비즈니스 로직
    └── prompts.py         # 프롬프트 템플릿

frontend/src/
├── components/chatbot/    # 채팅 UI 컴포넌트
├── api/chatApi.ts         # API 호출 레이어
├── pages/user/ChatBotPage.jsx
└── store/chatStore.js     # Zustand 상태 관리
```

## 주요 기능

- SSE(Server-Sent Events) 기반 스트리밍 응답
- 지역별 매출/가맹점 데이터 기반 질의응답
- 차트 데이터 자동 생성 (Bar, Line, Doughnut)
- 인텐트 분류 기반 맞춤 응답
