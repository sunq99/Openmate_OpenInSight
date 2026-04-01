import api from './axiosInstance'
import type { AxiosResponse } from 'axios'

export interface ChatSendRequest {
  message: string
  conversation_id?: string | null
}

export interface ChatSendResponse {
  reply: string
  conversation_id: string
  chart_type?: 'bar' | 'line' | null
  chart_data?: { labels: string[]; datasets: any[] } | null
}

export interface ChatStreamMetadata {
  type: 'metadata'
  conversation_id: string
  chart_type?: 'bar' | 'line' | null
  chart_data?: { labels: string[]; datasets: any[] } | null
  suggested_question?: string | null
  _intent?: string | null
}

export interface ChatFeedbackRequest {
  rating: 1 | -1
  question: string
  answer: string
}

/** 챗봇 메시지 전송 및 응답 수신 */
export const sendMessage = (
  data: ChatSendRequest,
): Promise<AxiosResponse<ChatSendResponse>> => api.post('/chat/send', data)

/** 챗봇 SSE 스트리밍 메시지 전송 */
export const streamMessage = async (
  data: ChatSendRequest,
  onToken: (token: string) => void,
  onMetadata: (meta: ChatStreamMetadata) => void,
  onDone: () => void,
  onError: (err: string) => void,
  signal?: AbortSignal,
): Promise<void> => {
  const token = localStorage.getItem('rim:v1:token')
  let res: Response
  try {
    res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
      signal,
    })
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') return
    onError(err instanceof Error ? err.message : '네트워크 오류가 발생했습니다.')
    return
  }

  if (!res.ok) {
    try {
      const errBody = await res.json()
      onError(errBody?.detail ?? `서버 오류 (${res.status})`)
    } catch {
      onError(`서버 오류 (${res.status})`)
    }
    return
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  // abort() 호출 시 pending 상태의 reader.read()를 즉시 깨움
  // (signal.aborted 체크만으로는 이미 await 중인 read()가 깨어나지 않음)
  const onAbort = () => reader.cancel()
  signal?.addEventListener('abort', onAbort, { once: true })

  try {
    while (true) {
      if (signal?.aborted) break
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''
      for (const part of parts) {
        if (!part.startsWith('data: ')) continue
        try {
          const parsed = JSON.parse(part.slice(6))
          if (parsed.type === 'token') onToken(parsed.content)
          else if (parsed.type === 'metadata') onMetadata(parsed as ChatStreamMetadata)
          else if (parsed.type === 'done') onDone()
          else if (parsed.type === 'error') onError(parsed.message)
        } catch (e) {
          console.warn('[chatApi] SSE 파싱 오류:', e, part)
        }
      }
    }
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') return
    throw err
  } finally {
    signal?.removeEventListener('abort', onAbort)
    reader.cancel()
  }
}

/** 대화 이력 서버 삭제 */
export const clearConversation = (
  conversationId: string,
): Promise<AxiosResponse<{ message: string }>> =>
  api.delete(`/chat/conversation/${conversationId}`)

/** 챗봇 답변 평가 전송 (1=좋아요, -1=싫어요) */
export const submitFeedback = (
  data: ChatFeedbackRequest,
): Promise<AxiosResponse<{ message: string; success: boolean }>> =>
  api.post('/chat/feedback', data)
