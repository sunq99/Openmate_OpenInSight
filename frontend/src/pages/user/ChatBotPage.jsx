import { useRef, useEffect, useState } from 'react'
import { Send, Square, Trash2, ChevronDown, ChevronUp, ArrowRight, Sparkles, Bot } from 'lucide-react'
import useChatStore from '../../store/chatStore'
import ChatBotMessage from '../../components/chatbot/ChatBotMessage'
import ChatBotTypingIndicator from '../../components/chatbot/ChatBotTypingIndicator'

const SAMPLE_QUESTIONS = [
  '내가 확인할 수 있는 축제 목록 알려줘',
  '홍천읍에서 진행한 축제 방문인구 알려줘',
  '홍천읍에서 최근에 진행한 축제 연령대별 매출 알려줘',
  '홍천읍에서 진행한 축제 성별 방문인구 비교해줘',
]

const POSSIBLE_QUESTIONS = [
  '특정 축제의 시간대별 방문인구 조회',
  '연령대·성별 매출 분석',
  '지역별 축제 목록 및 기간 조회',
  '연도별·기간별 축제 통계 비교',
]

const IMPOSSIBLE_QUESTIONS = [
  '외부 기관 데이터 (타 지자체, 국가 통계 등)',
  '실시간 현황 조회',
  '미래 예측 및 전망',
  '시스템에 등록되지 않은 축제 정보',
]

/* ─── 봇 아바타 (헤더/Hero 공용) ─── */
function BotAvatar({ size = 'md' }) {
  const sizeMap = {
    sm: { outer: 'w-8 h-8', icon: 14 },
    md: { outer: 'w-12 h-12', icon: 22 },
    lg: { outer: 'w-16 h-16', icon: 30 },
  }
  const { outer, icon } = sizeMap[size]
  return (
    <div
      className={`${outer} rounded-full flex items-center justify-center flex-shrink-0 shadow-md`}
      style={{ background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)' }}
    >
      <Bot size={icon} className="text-white" />
    </div>
  )
}

/* ─── 온라인 상태 Dot ─── */
function OnlineDot() {
  return (
    <span className="relative flex h-2.5 w-2.5">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-success" />
    </span>
  )
}

/* ─── 가이드 패널 (가능/불가 질문) ─── */
function GuidePanel() {
  return (
    <div className="grid grid-cols-2 gap-3">
      {/* 가능한 질문 */}
      <div
        className="rounded-xl p-3 border-l-4 border-success"
        style={{ backgroundColor: 'rgba(22,163,74,0.06)' }}
      >
        <p className="text-sm font-semibold text-success mb-2 flex items-center gap-1">
          <span>✅</span> 가능한 질문
        </p>
        <ul className="space-y-1.5">
          {POSSIBLE_QUESTIONS.map((item) => (
            <li key={item} className="text-sm text-gray-900 flex gap-1.5 items-start font-medium">
              <span className="text-success mt-0.5 leading-none">·</span>
              {item}
            </li>
          ))}
        </ul>
      </div>

      {/* 불가능한 질문 */}
      <div
        className="rounded-xl p-3 border-l-4 border-danger"
        style={{ backgroundColor: 'rgba(220,38,38,0.06)' }}
      >
        <p className="text-sm font-semibold text-danger mb-2 flex items-center gap-1">
          <span>❌</span> 지원하지 않는 질문
        </p>
        <ul className="space-y-1.5">
          {IMPOSSIBLE_QUESTIONS.map((item) => (
            <li key={item} className="text-sm text-gray-900 flex gap-1.5 items-start font-medium">
              <span className="text-danger mt-0.5 leading-none">·</span>
              {item}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default function ChatBotPage() {
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const [showGuide, setShowGuide] = useState(true)
  const messages = useChatStore((s) => s.messages)
  const inputValue = useChatStore((s) => s.inputValue)
  const isLoading = useChatStore((s) => s.isLoading)
  const setInputValue = useChatStore((s) => s.setInputValue)
  const sendMessage = useChatStore((s) => s.sendMessage)
  const stopStreaming = useChatStore((s) => s.stopStreaming)
  const clearMessages = useChatStore((s) => s.clearMessages)

  useEffect(() => {
    document.title = 'AI 데이터 분석 Agent - RIS'
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  useEffect(() => {
    if (!isLoading) inputRef.current?.focus()
  }, [isLoading])

  useEffect(() => {
    if (messages.length === 1) setShowGuide(false)
  }, [messages])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!inputValue.trim() || isLoading) return
    sendMessage(inputValue.trim())
  }

  const isEmpty = messages.length === 0

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)]">

      {/* ── 헤더 ── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-primary-200 bg-white rounded-t-[var(--radius-lg)]">
        <div className="flex items-center gap-3">
          <BotAvatar size="sm" />
          <div>
            <h1 className="text-sm font-bold text-primary-900 leading-tight">
              AI 데이터 분석 Agent
            </h1>
            {!isEmpty && (
              <div className="flex items-center gap-1.5 mt-0.5">
                <OnlineDot />
                <span className="text-xs text-success font-medium">온라인</span>
              </div>
            )}
          </div>
        </div>

        <button
          onClick={clearMessages}
          disabled={isEmpty}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-primary-400
                     hover:text-danger hover:bg-red-50 rounded-[var(--radius-sm)] transition-all
                     disabled:opacity-40 disabled:cursor-not-allowed border border-transparent
                     hover:border-danger/20"
          aria-label="대화 초기화"
        >
          <Trash2 size={13} aria-hidden="true" />
          초기화
        </button>
      </div>

      {/* ── 채팅 중 가이드 토글 ── */}
      {!isEmpty && (
        <div className="px-4 py-2 border-b border-primary-200 bg-white">
          <button
            onClick={() => setShowGuide((v) => !v)}
            className="flex items-center gap-1 text-xs text-primary-400 hover:text-accent-600
                       transition-colors mx-auto font-medium"
          >
            {showGuide ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            어떤 질문이 가능한가요?
          </button>
          {showGuide && (
            <div className="mt-2.5 max-w-lg mx-auto">
              <GuidePanel />
            </div>
          )}
        </div>
      )}

      {/* ── 메시지 영역 ── */}
      <div
        className="flex-1 min-h-0 overflow-y-auto bg-bg-app"
        role="log"
        aria-live="polite"
        aria-label="대화 내역"
      >
        {/* ── 빈 화면 Hero ── */}
        {isEmpty && (
          <div className="flex flex-col items-center px-4 py-10 gap-6 w-full">

            {/* 가이드 패널 */}
            <div className="w-full">
              <button
                onClick={() => setShowGuide((v) => !v)}
                className="flex items-center gap-1 text-xs text-primary-400 hover:text-accent-600
                           transition-colors mx-auto mb-2.5 font-medium"
              >
                {showGuide ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                어떤 질문이 가능한가요?
              </button>
              {showGuide && <GuidePanel />}
            </div>

            {/* Hero 헤더 */}
            <div className="flex flex-col items-center gap-3 text-center">
              <div className="relative">
                <BotAvatar size="lg" />
                <div
                  className="absolute inset-0 rounded-full -z-10 blur-md opacity-40 scale-110"
                  style={{ background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)' }}
                />
              </div>
              <div>
                <h2 className="text-xl font-bold text-primary-900 flex items-center gap-2 justify-center">
                  AI 데이터 분석 Agent
                  <Sparkles size={18} className="text-accent-500" />
                </h2>
                <p className="text-sm text-gray-700 mt-1 font-medium">
                  지역 축제 데이터를 바탕으로 분석을 도와드립니다
                </p>
              </div>
            </div>

            {/* 샘플 질문 */}
            <div className="w-full">
              <p className="text-xs font-semibold text-primary-400 mb-2.5 text-center flex items-center justify-center gap-1">
                💡
                이런 질문을 해보세요
              </p>
              <div className="grid grid-cols-2 gap-2">
                {SAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => sendMessage(q)}
                    disabled={isLoading}
                    className="group px-3 py-2.5 text-sm text-left text-gray-900 font-medium bg-white
                               border border-primary-200 rounded-[var(--radius-md)]
                               hover:border-accent-500 hover:text-accent-600
                               hover:shadow-md transition-all duration-200
                               disabled:opacity-40 disabled:cursor-not-allowed
                               flex items-start justify-between gap-1"
                  >
                    <span className="leading-snug flex-1">{q}</span>
                    <ArrowRight
                      size={13}
                      className="flex-shrink-0 mt-0.5 text-primary-400
                                 group-hover:text-accent-500
                                 group-hover:translate-x-0.5
                                 transition-all duration-200"
                    />
                  </button>
                ))}
              </div>
            </div>

          </div>
        )}

        {/* 메시지 목록 */}
        <div className="p-4 space-y-3">
          {messages.map((msg) => (
            <ChatBotMessage key={msg.id} message={msg} />
          ))}
          {isLoading && !messages.some((m) => m.isStreaming) && <ChatBotTypingIndicator />}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* ── 입력 영역 ── */}
      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 px-3 py-3 border-t border-primary-200 bg-white rounded-b-[var(--radius-lg)]"
      >
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="메시지를 입력하세요..."
          className="flex-1 px-4 py-2 text-[17px] border border-primary-200 rounded-full
                     focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20
                     bg-bg-app text-primary-900 placeholder:text-primary-400
                     transition-all duration-200"
          disabled={isLoading}
          aria-label="챗봇 메시지 입력"
        />
        {isLoading ? (
          <button
            type="button"
            onClick={stopStreaming}
            className="p-2.5 rounded-full text-white shadow-sm
                       transition-all duration-200 hover:scale-105 active:scale-95
                       focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-1"
            style={{ background: 'linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)' }}
            aria-label="스트리밍 중단"
          >
            <Square size={16} aria-hidden="true" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!inputValue.trim()}
            className="p-2.5 rounded-full text-white shadow-sm
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transition-all duration-200 hover:scale-105 active:scale-95
                       focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-1"
            style={{
              background: !inputValue.trim()
                ? '#9fb3c8'
                : 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)',
            }}
            aria-label="메시지 전송"
          >
            <Send size={16} aria-hidden="true" />
          </button>
        )}
      </form>

    </div>
  )
}
