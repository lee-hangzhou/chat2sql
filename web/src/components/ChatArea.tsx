import { MessageSquare } from 'lucide-react'
import { useChatStore } from '../stores/chat'
import { useAuthStore } from '../stores/auth'
import MessageList from './MessageList'
import MessageInput from './MessageInput'
import NodeProgress from './NodeProgress'

export default function ChatArea() {
  const { isAuthenticated } = useAuthStore()
  const {
    activeId,
    messages,
    currentNode,
    nodeSteps,
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

  const showProgress = nodeSteps.length > 0

  return (
    <div className="flex flex-1 overflow-hidden bg-[var(--color-chat-bg)]">
      {/* 对话区域 */}
      <div className="flex flex-1 flex-col min-w-0">
        <MessageList
          messages={messages}
          currentNode={currentNode}
          sending={sending}
          executeResult={executeResult}
        />

        <MessageInput
          onSend={sendMessage}
          disabled={sending}
          placeholder={
            sending ? '正在处理中...' : '输入你的问题，按 Enter 发送'
          }
        />
      </div>

      {/* 节点进度面板 */}
      {showProgress && (
        <div className="w-64 shrink-0 border-l border-gray-200 bg-white p-4 overflow-y-auto">
          <h3 className="mb-4 text-sm font-medium text-gray-500">执行进度</h3>
          <NodeProgress steps={nodeSteps} />
        </div>
      )}
    </div>
  )
}
