import { MessageSquare } from 'lucide-react'
import { useChatStore } from '../stores/chat'
import { useAuthStore } from '../stores/auth'
import MessageList from './MessageList'
import MessageInput from './MessageInput'
import ResultTable from './ResultTable'

export default function ChatArea() {
  const { isAuthenticated } = useAuthStore()
  const {
    activeId,
    messages,
    currentNode,
    sending,
    executeResult,
    sendMessage,
  } = useChatStore()

  if (!isAuthenticated) {
    return (
      <div className="flex flex-1 items-center justify-center bg-[var(--color-chat-bg)]">
        <div className="text-center text-gray-400">
          <MessageSquare size={48} className="mx-auto mb-4" />
          <p className="text-lg">请先登录</p>
        </div>
      </div>
    )
  }

  if (!activeId) {
    return (
      <div className="flex flex-1 items-center justify-center bg-[var(--color-chat-bg)]">
        <div className="text-center text-gray-400">
          <MessageSquare size={48} className="mx-auto mb-4" />
          <p className="text-lg">选择一个对话或新建对话开始</p>
          <p className="mt-1 text-sm">用自然语言描述你想查询的数据</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col bg-[var(--color-chat-bg)]">
      <MessageList
        messages={messages}
        currentNode={currentNode}
        sending={sending}
      />

      {/* SQL 执行结果表格 */}
      {executeResult && executeResult.length > 0 && (
        <div className="mx-auto w-full max-w-3xl shrink-0 px-4 pb-2">
          <p className="mb-2 text-xs font-medium text-gray-500">
            查询结果（{executeResult.length} 行）
          </p>
          <ResultTable data={executeResult} />
        </div>
      )}

      <MessageInput
        onSend={sendMessage}
        disabled={sending}
        placeholder={
          sending ? '正在处理中...' : '输入你的问题，按 Enter 发送'
        }
      />
    </div>
  )
}
