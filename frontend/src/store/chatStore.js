import { create } from 'zustand'
import * as chatApi from '../api/chatApi'

let nextMessageId = 0

// ─── 타자기 효과 설정 ───────────────────────────────────
const TYPEWRITER_DELAY_MS = 15       // 글자 하나당 표시 간격 (ms) — 값이 클수록 느림
const RETRY_MAX = 2                  // 최대 재시도 횟수 (총 3번 시도)
const RETRY_DELAYS_MS = [1500, 3000] // 재시도별 대기 시간 (exponential backoff)

// 메시지 ID별 글자 큐 / 대기 중인 액션 목록
const _charQueues = new Map()    // botMsgId → string[]
const _pendingActions = new Map() // botMsgId → action[]  ← 배열로 변경 (덮어쓰기 방지)

function _applyAction(botMsgId, action, set) {
  if (action.type === 'metadata') {
    const meta = action.data
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === botMsgId
          ? {
              ...m,
              isStreaming: false,
              chart_type: meta.chart_type ?? null,
              chart_data: meta.chart_data ?? null,
              active_chart_type: meta.chart_type ?? null,
              suggested_question: meta.suggested_question ?? null,
              intent: meta._intent?.replace(/_/g, ' ') ?? null,
            }
          : m,
      ),
      conversationId: meta.conversation_id ?? s.conversationId,
      isLoading: false,
      // 타자기 완료 시점에 _currentBotMsgId 해제
      _currentBotMsgId: s._currentBotMsgId === botMsgId ? null : s._currentBotMsgId,
    }))
  } else if (action.type === 'done') {
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === botMsgId ? { ...m, isStreaming: false } : m,
      ),
      isLoading: false,
      _currentBotMsgId: s._currentBotMsgId === botMsgId ? null : s._currentBotMsgId,
    }))
  } else if (action.type === 'error') {
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === botMsgId
          ? { ...m, isStreaming: false, content: m.content || action.message }
          : m,
      ),
      isLoading: false,
      _currentBotMsgId: s._currentBotMsgId === botMsgId ? null : s._currentBotMsgId,
    }))
  }
}

function _flushQueue(botMsgId, set) {
  const chars = _charQueues.get(botMsgId)
  if (!chars || chars.length === 0) {
    // 글자 큐 소진 → 대기 액션을 순서대로 처리
    const actions = _pendingActions.get(botMsgId)
    if (actions && actions.length > 0) {
      const action = actions.shift()
      _applyAction(botMsgId, action, set)
      if (actions.length > 0) {
        // 남은 액션이 있으면 계속 처리
        setTimeout(() => _flushQueue(botMsgId, set), 0)
      } else {
        _pendingActions.delete(botMsgId)
        _charQueues.delete(botMsgId)
      }
    }
    return
  }
  const char = chars.shift()
  set((s) => ({
    messages: s.messages.map((m) =>
      m.id === botMsgId ? { ...m, content: m.content + char } : m,
    ),
  }))
  setTimeout(() => _flushQueue(botMsgId, set), TYPEWRITER_DELAY_MS)
}

function _enqueueToken(botMsgId, token, set) {
  if (!_charQueues.has(botMsgId)) _charQueues.set(botMsgId, [])
  const chars = _charQueues.get(botMsgId)
  const wasEmpty = chars.length === 0
  chars.push(...token.split(''))
  if (wasEmpty) setTimeout(() => _flushQueue(botMsgId, set), TYPEWRITER_DELAY_MS)
}

function _enqueueAction(botMsgId, action, set) {
  const chars = _charQueues.get(botMsgId)
  const pending = _pendingActions.get(botMsgId)
  if ((!chars || chars.length === 0) && (!pending || pending.length === 0)) {
    // 글자 큐와 액션 큐 모두 비어있으면 즉시 적용
    _charQueues.delete(botMsgId)
    _applyAction(botMsgId, action, set)
  } else {
    if (!_pendingActions.has(botMsgId)) _pendingActions.set(botMsgId, [])
    _pendingActions.get(botMsgId).push(action)
  }
}
// ────────────────────────────────────────────────────────

const useChatStore = create((set, get) => ({
  isOpen: false,
  inputValue: '',
  messages: [],
  isLoading: false,
  conversationId: null,
  _abortController: null,
  _currentBotMsgId: null,

  toggleChat: () => set((s) => ({ isOpen: !s.isOpen })),
  openChat: () => set({ isOpen: true }),
  closeChat: () => set({ isOpen: false }),
  setInputValue: (v) => set({ inputValue: v }),

  sendMessage: async (content) => {
    // 이전 요청이 남아 있으면 먼저 중단
    const prevController = get()._abortController
    if (prevController) prevController.abort()

    const controller = new AbortController()
    set({ _abortController: controller })

    const userMessage = {
      id: ++nextMessageId,
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    }

    // 봇 메시지 플레이스홀더 (빈 content로 스트리밍 시작)
    const botMsgId = ++nextMessageId
    const botMessagePlaceholder = {
      id: botMsgId,
      role: 'bot',
      content: '',
      isStreaming: true,
      isReconnecting: false,
      intent: null,
      chart_type: null,
      chart_data: null,
      active_chart_type: null,
      suggested_question: null,
      timestamp: new Date().toISOString(),
      feedback: null,
      question: content,
    }

    set((s) => ({
      messages: [...s.messages, userMessage, botMessagePlaceholder],
      inputValue: '',
      isLoading: true,
      _currentBotMsgId: botMsgId,
    }))

    const { conversationId } = get()

    let attempt = 0
    while (attempt <= RETRY_MAX) {
      // 루프 시작: 큐 초기화
      _charQueues.set(botMsgId, [])
      _pendingActions.delete(botMsgId)

      // 재시도 시 메시지 상태 초기화
      if (attempt > 0) {
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === botMsgId
              ? { ...m, content: '', isStreaming: true, isReconnecting: false }
              : m,
          ),
        }))
      }

      let streamError = null

      await chatApi.streamMessage(
        { message: content, conversation_id: conversationId },
        (token) => { if (!controller.signal.aborted) _enqueueToken(botMsgId, token, set) },
        (meta)  => { if (!controller.signal.aborted) _enqueueAction(botMsgId, { type: 'metadata', data: meta }, set) },
        ()      => { if (!controller.signal.aborted) _enqueueAction(botMsgId, { type: 'done' }, set) },
        (err)   => { streamError = err },  // 바로 처리하지 않고 기록만
        controller.signal,
      ).catch((err) => {
        if (!(err instanceof Error && err.name === 'AbortError')) {
          streamError = err?.message ?? '알 수 없는 오류'
        }
      })

      // abort → 재시도 없음
      if (controller.signal.aborted) {
        if (get()._currentBotMsgId === botMsgId) {
          _charQueues.delete(botMsgId)
          _pendingActions.delete(botMsgId)
          set((s) => ({
            messages: s.messages.map((m) =>
              m.id === botMsgId
                ? { ...m, isStreaming: false, isReconnecting: false }
                : m,
            ),
            isLoading: false, _abortController: null, _currentBotMsgId: null,
          }))
        }
        return
      }

      // 성공
      if (!streamError) {
        set({ _abortController: null })
        return
      }

      // 에러 → 재시도 판단
      attempt++
      _charQueues.delete(botMsgId)
      _pendingActions.delete(botMsgId)

      if (attempt <= RETRY_MAX) {
        // "재연결 중..." UI 표시 후 대기
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === botMsgId ? { ...m, isReconnecting: true, isStreaming: true } : m,
          ),
        }))
        await new Promise((r) => setTimeout(r, RETRY_DELAYS_MS[attempt - 1] ?? 3000))

        // 대기 중 abort 확인
        if (controller.signal.aborted) {
          _charQueues.delete(botMsgId)
          _pendingActions.delete(botMsgId)
          set((s) => ({
            messages: s.messages.map((m) =>
              m.id === botMsgId ? { ...m, isStreaming: false, isReconnecting: false } : m,
            ),
            isLoading: false, _abortController: null, _currentBotMsgId: null,
          }))
          return
        }
      } else {
        // 모든 재시도 실패 → 에러 메시지 표시
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === botMsgId
              ? {
                  ...m,
                  isStreaming: false, isReconnecting: false,
                  content: '죄송합니다. 연결이 불안정하여 응답을 받지 못했습니다. 잠시 후 다시 시도해 주세요.',
                }
              : m,
          ),
          isLoading: false, _abortController: null, _currentBotMsgId: null,
        }))
      }
    }
  },

  stopStreaming: () => {
    const { _abortController, _currentBotMsgId } = get()

    // 진행 중인 것이 없으면 무시
    if (!_abortController && _currentBotMsgId == null) return

    // fetch 중단 (아직 스트리밍 중인 경우)
    if (_abortController) _abortController.abort()

    // 타자기 큐 버리기 (남은 글자는 표시하지 않고 현재 상태에서 중단)
    if (_currentBotMsgId != null) {
      _charQueues.delete(_currentBotMsgId)
      _pendingActions.delete(_currentBotMsgId)

      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === _currentBotMsgId
            ? { ...m, isStreaming: false, isReconnecting: false }
            : m,
        ),
        isLoading: false,
        _abortController: null,
        _currentBotMsgId: null,
      }))
    } else {
      set({ isLoading: false, _abortController: null })
    }
  },

  submitFeedback: async (messageId, rating) => {
    const { messages } = get()
    const msg = messages.find((m) => m.id === messageId)
    if (!msg || msg.feedback !== null) return

    // 낙관적 UI 업데이트
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === messageId ? { ...m, feedback: rating } : m,
      ),
    }))

    try {
      await chatApi.submitFeedback({
        rating,
        question: msg.question ?? '',
        answer: msg.content,
      })
    } catch {
      // 실패 시 롤백
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === messageId ? { ...m, feedback: null } : m,
        ),
      }))
    }
  },

  setActiveChartType: (messageId, chartType) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === messageId ? { ...m, active_chart_type: chartType } : m,
      ),
    })),

  clearMessages: () => {
    const { conversationId } = get()
    if (conversationId) {
      chatApi.clearConversation(conversationId).catch(() => {})
    }
    set({ messages: [], conversationId: null, inputValue: '' })
  },
}))

export default useChatStore
