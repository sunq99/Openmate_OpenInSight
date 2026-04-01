import { Bot } from 'lucide-react'

export default function ChatBotTypingIndicator() {
  return (
    <div className="flex items-start gap-2.5 justify-start">
      <div
        className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center mt-0.5 shadow-xs"
        style={{ background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)' }}
      >
        <Bot size={14} className="text-white" />
      </div>
      <div
        className="bg-white border border-primary-100 rounded-[var(--radius-md)] rounded-bl-[var(--radius-xs)] px-4 py-2.5 flex items-center gap-1.5 shadow-xs"
        aria-label="응답 중..."
      >
        <span className="w-2 h-2 bg-primary-300 rounded-full animate-bounce [animation-delay:0ms]" />
        <span className="w-2 h-2 bg-primary-300 rounded-full animate-bounce [animation-delay:150ms]" />
        <span className="w-2 h-2 bg-primary-300 rounded-full animate-bounce [animation-delay:300ms]" />
      </div>
    </div>
  )
}
