import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Bot, ArrowRight, ThumbsUp, ThumbsDown, Copy, Check } from 'lucide-react'
import BarChart from '../charts/BarChart'
import LineChart from '../charts/LineChart'
import DoughnutChart from '../charts/DoughnutChart'
import useChatStore from '../../store/chatStore'
import { COLORS } from '../charts/chartColors'

const CHART_TYPES = [
  { key: 'bar', label: '막대' },
  { key: 'line', label: '선형' },
  { key: 'doughnut', label: '도넛' },
]

// 슬라이스 수가 많을 경우(시간대·요일 등) 단일 색상 그라데이션 적용 임계값
const GRADIENT_THRESHOLD = 6

/**
 * n개의 슬라이스에 대해 start → end 색상 보간 배열 반환
 * start/end: [r, g, b] 튜플
 */
function buildGradientColors(n, start, end, alpha = 0.82) {
  if (n === 1) return [`rgba(${start.join(',')},${alpha})`]
  return Array.from({ length: n }, (_, i) => {
    const t = i / (n - 1)
    const r = Math.round(start[0] + (end[0] - start[0]) * t)
    const g = Math.round(start[1] + (end[1] - start[1]) * t)
    const b = Math.round(start[2] + (end[2] - start[2]) * t)
    return `rgba(${r},${g},${b},${alpha})`
  })
}

// 시간대 라벨 감지 (예: "6시", "23시", "06:00")
const isTimeLabel = (label) => /^\d{1,2}시$/.test(String(label))

function toDoughnutData(chartData) {
  if (!chartData || !chartData.datasets) return chartData

  // 여러 datasets → 각 dataset을 하나의 슬라이스로 (예: 일별 추이의 남성/여성/총 series)
  if (chartData.datasets.length > 1) {
    const labels = chartData.datasets.map((ds, i) => ds.label ?? `항목 ${i + 1}`)
    const data = chartData.datasets.map((ds) =>
      Array.isArray(ds.data) ? ds.data.reduce((sum, v) => sum + (Number(v) || 0), 0) : 0,
    )
    return {
      labels,
      datasets: [{ data, backgroundColor: COLORS.slice(0, data.length), borderWidth: 0 }],
    }
  }

  // 단일 dataset + 다수 labels → chartData.labels를 슬라이스 label로 사용
  const ds = chartData.datasets[0]
  const rawData = Array.isArray(ds.data) ? ds.data.map((v) => Number(v) || 0) : []
  const sliceLabels =
    Array.isArray(chartData.labels) && chartData.labels.length === rawData.length
      ? chartData.labels
      : rawData.map((_, i) => ds.label ?? `항목 ${i + 1}`)

  // 슬라이스가 많거나 시간대 라벨이면 단일 색 그라데이션 적용 (연한파랑 → 진한파랑)
  const useGradient =
    rawData.length > GRADIENT_THRESHOLD ||
    (sliceLabels.length > 0 && isTimeLabel(sliceLabels[0]))
  const colors = useGradient
    ? buildGradientColors(rawData.length, [147, 197, 253], [29, 78, 216])
    : COLORS.slice(0, rawData.length)

  return {
    labels: sliceLabels,
    datasets: [{ data: rawData, backgroundColor: colors, borderWidth: 0 }],
  }
}

export default function ChatBotMessage({ message }) {
  const isUser = message.role === 'user'
  const sendMessage = useChatStore((s) => s.sendMessage)
  const submitFeedback = useChatStore((s) => s.submitFeedback)
  const setActiveChartType = useChatStore((s) => s.setActiveChartType)
  const isLoading = useChatStore((s) => s.isLoading)
  const [copied, setCopied] = useState(false)

  // 복사 시 제외할 고정 footer 문장 목록
  const COPY_EXCLUDED_SUFFIXES = [
    '\n> 특정 축제의 상세 정보나 통계가 필요하면 축제명을 말씀해주세요.',
  ]

  const handleCopy = () => {
    let text = message.content
    for (const suffix of COPY_EXCLUDED_SUFFIXES) {
      if (text.endsWith(suffix)) {
        text = text.slice(0, -suffix.length).trimEnd()
      }
    }

    const onSuccess = () => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }

    // HTTPS/localhost: Clipboard API 사용
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(onSuccess).catch(() => fallbackCopy(text, onSuccess))
    } else {
      fallbackCopy(text, onSuccess)
    }
  }

  const fallbackCopy = (text, onSuccess) => {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.cssText = 'position:absolute;left:-9999px;top:-9999px;width:1px;height:1px'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    try {
      const ok = document.execCommand('copy')
      if (ok) onSuccess()
      else console.error('복사 실패: execCommand returned false')
    } catch (e) {
      console.error('복사 실패:', e)
    } finally {
      document.body.removeChild(textarea)
    }
  }

  const timestamp = new Date(message.timestamp).toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <div className={`flex items-start gap-2.5 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {/* 봇 아이콘 */}
      {!isUser && (
        <div
          className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center mt-0.5 shadow-xs"
          style={{ background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)' }}
        >
          <Bot size={14} className="text-white" />
        </div>
      )}

      {isUser ? (
        /* 사용자 메시지: 버블 + 타임스탬프(버블 밖) */
        <div className="flex flex-col items-end gap-1 max-w-[80%]">
          <div
            className="px-3.5 py-2.5 text-[17px] leading-relaxed text-white rounded-[var(--radius-md)] rounded-br-[var(--radius-xs)]"
            style={{ background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)' }}
          >
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
          <p className="text-[11px] text-gray-900 pr-0.5">{timestamp}</p>
        </div>
      ) : (
        /* 봇 메시지: [intent뱃지] → 버블 → 타임스탬프(버블 밖) */
        <div className="flex flex-col gap-1 w-[80%]">
          {/* 질문 의도 뱃지 — 봇 아이콘 옆(상단) */}
          {!message.isStreaming && message.intent && (
            <span className="self-start px-2 py-0.5 text-[12px] font-medium rounded-full bg-blue-50 text-blue-600 border border-blue-200">
              {message.intent}
            </span>
          )}

          {/* 버블 */}
          <div className="px-3.5 py-2.5 text-[17px] leading-relaxed bg-bg-app text-primary-800 rounded-[var(--radius-md)] rounded-bl-[var(--radius-xs)]">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => <h1 className="text-[20px] font-bold mt-2 mb-1 text-primary-900">{children}</h1>,
                h2: ({ children }) => <h2 className="text-[19px] font-bold mt-2 mb-1 text-primary-900">{children}</h2>,
                h3: ({ children }) => <h3 className="text-[18px] font-semibold mt-1 mb-1 text-primary-800">{children}</h3>,
                p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                ul: ({ children }) => <ul className="list-disc list-inside mb-1 space-y-0.5">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal list-inside mb-1 space-y-0.5">{children}</ol>,
                li: ({ children }) => <li className="text-[17px]">{children}</li>,
                table: ({ children }) => (
                  <div className="overflow-x-auto my-3">
                    <table className="text-[15px] w-full">{children}</table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead style={{ borderBottom: '2px solid #94a3b8' }}>{children}</thead>
                ),
                th: ({ children }) => (
                  <th className="px-3 py-2.5 text-left font-bold text-gray-900 whitespace-nowrap">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-3 py-2.5 text-gray-800 align-top" style={{ borderBottom: '1px solid #e2e8f0' }}>
                    {children}
                  </td>
                ),
                tr: ({ children }) => (
                  <tr className="hover:bg-slate-50/60 transition-colors">{children}</tr>
                ),
                code: ({ children }) => <code className="bg-primary-50 text-accent-700 px-1 rounded-[var(--radius-xs)] text-[15px] font-mono">{children}</code>,
                strong: ({ children }) => <strong className="font-semibold text-primary-900">{children}</strong>,
              }}
            >
              {message.content}
            </ReactMarkdown>
            {/* 재연결 중 배너 */}
            {message.isReconnecting && (
              <span className="flex items-center gap-1.5 py-1 text-[14px] text-amber-600 font-medium">
                <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse" />
                재연결 중...
              </span>
            )}
            {/* 첫 응답 대기 (점 세 개) */}
            {message.isStreaming && !message.isReconnecting && !message.content && (
              <span className="flex items-center gap-1.5 py-0.5">
                <span className="w-2 h-2 bg-primary-300 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 bg-primary-300 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 bg-primary-300 rounded-full animate-bounce [animation-delay:300ms]" />
              </span>
            )}
            {/* 타자기 커서 */}
            {message.isStreaming && !message.isReconnecting && message.content && (
              <span className="inline-block w-0.5 h-[1em] bg-primary-400 animate-pulse ml-0.5 align-middle" />
            )}
            {/* 차트 */}
            {!message.isStreaming && message.chart_type && message.chart_data && (
              <div className="mt-3 p-2 bg-primary-50/50 rounded-[var(--radius-sm)]">
                <div className="flex justify-end gap-1 mb-2">
                  {CHART_TYPES.map(({ key, label }) => {
                    const isActive = (message.active_chart_type ?? message.chart_type) === key
                    return (
                      <button
                        key={key}
                        onClick={() => setActiveChartType(message.id, key)}
                        className={`px-2.5 py-1 text-[12px] font-medium rounded-md border transition-all duration-150
                          ${isActive
                            ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                            : 'bg-white text-gray-500 border-primary-200 hover:bg-primary-50 hover:text-primary-700 hover:border-primary-300'
                          }`}
                      >
                        {label}
                      </button>
                    )
                  })}
                </div>
                {(message.active_chart_type ?? message.chart_type) === 'bar' && (
                  <BarChart data={message.chart_data} />
                )}
                {(message.active_chart_type ?? message.chart_type) === 'line' && (
                  <LineChart data={message.chart_data} />
                )}
                {(message.active_chart_type ?? message.chart_type) === 'doughnut' && (
                  <DoughnutChart data={toDoughnutData(message.chart_data)} />
                )}
              </div>
            )}
            {/* 추천 질문 */}
            {!message.isStreaming && message.suggested_question && (
              <div className="mt-3 pt-3 border-t border-primary-100">
                <p className="text-[15px] text-black mb-1.5">💡 이런 것도 물어보세요 <span className="text-primary-400">(현재 BETA 버전으로 정확한 답볍이 어려울 수 있습니다.)</span></p>
                <button
                  onClick={() => sendMessage(message.suggested_question)}
                  disabled={isLoading}
                  className="group flex items-center justify-between gap-2 w-full px-3 py-2
                             text-[15px] text-left font-medium text-gray-800
                             bg-primary-50 hover:bg-blue-50
                             border border-primary-200 hover:border-blue-400
                             rounded-lg transition-all duration-200
                             disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <span>{message.suggested_question}</span>
                  <ArrowRight
                    size={14}
                    className="flex-shrink-0 text-primary-400 group-hover:text-blue-500
                               group-hover:translate-x-0.5 transition-all duration-200"
                  />
                </button>
              </div>
            )}
            {/* 피드백 */}
            {!message.isStreaming && (
              <div className="mt-2 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="text-[13px] text-gray-400">이 답변이 도움이 됐나요?</span>
                  <button
                    onClick={() => submitFeedback(message.id, 1)}
                    disabled={message.feedback !== null}
                    title="도움이 됐어요"
                    className={`p-1.5 rounded-md transition-all duration-150
                      ${message.feedback === 1
                        ? 'text-blue-600 bg-blue-50'
                        : 'text-gray-400 hover:text-blue-500 hover:bg-blue-50'}
                      disabled:cursor-default`}
                  >
                    <ThumbsUp size={14} />
                  </button>
                  <button
                    onClick={() => submitFeedback(message.id, -1)}
                    disabled={message.feedback !== null}
                    title="도움이 안 됐어요"
                    className={`p-1.5 rounded-md transition-all duration-150
                      ${message.feedback === -1
                        ? 'text-red-500 bg-red-50'
                        : 'text-gray-400 hover:text-red-400 hover:bg-red-50'}
                      disabled:cursor-default`}
                  >
                    <ThumbsDown size={14} />
                  </button>
                </div>
                <button
                  onClick={handleCopy}
                  title="답변 복사"
                  className={`flex items-center gap-1 px-2 py-1 text-[12px] rounded-md transition-all duration-150
                    ${copied
                      ? 'text-green-600 bg-green-50'
                      : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
                >
                  {copied ? <Check size={13} /> : <Copy size={13} />}
                  {copied ? '복사됨' : '복사'}
                </button>
              </div>
            )}
          </div>

          {/* 타임스탬프 — 버블 밖 */}
          {!message.isStreaming && (
            <p className="text-[11px] text-gray-900">{timestamp}</p>
          )}
        </div>
      )}
    </div>
  )
}
