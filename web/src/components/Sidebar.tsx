import { useState } from 'react'
import { DatabaseZap, MessageSquarePlus, Trash2 } from 'lucide-react'
import { syncSchema } from '../api/chat'
import { useChatStore } from '../stores/chat'

export default function Sidebar() {
  const {
    conversations,
    activeId,
    createConversation,
    selectConversation,
    deleteConversation,
    sending,
  } = useChatStore()

  const [syncing, setSyncing] = useState(false)

  const handleNew = async () => {
    if (sending) return
    await createConversation()
  }

  const handleSync = async () => {
    if (syncing) return
    setSyncing(true)
    try {
      const result = await syncSchema()
      alert(`同步完成，共 ${result.table_count} 张表`)
    } catch (e) {
      alert(`同步失败: ${e instanceof Error ? e.message : '未知错误'}`)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col bg-[var(--color-sidebar)] text-gray-200">
      {/* 新建对话 */}
      <div className="p-3">
        <button
          onClick={handleNew}
          disabled={sending}
          className="flex w-full items-center gap-2 rounded-lg border border-gray-600 px-4 py-2.5 text-sm hover:bg-[var(--color-sidebar-hover)] disabled:opacity-40"
        >
          <MessageSquarePlus size={18} />
          新建对话
        </button>
      </div>

      {/* 对话列表 */}
      <nav className="flex-1 overflow-y-auto px-2 pb-4">
        {conversations.map((conv) => (
          <div
            key={conv.id}
            className={`group relative my-0.5 flex cursor-pointer items-center rounded-lg px-3 py-2.5 text-sm transition-colors ${
              activeId === conv.id
                ? 'bg-[var(--color-sidebar-active)] text-white'
                : 'text-gray-300 hover:bg-[var(--color-sidebar-hover)]'
            }`}
            onClick={() => selectConversation(conv.id)}
          >
            <span className="flex-1 truncate">
              {conv.title || '新对话'}
            </span>

            <button
              onClick={(e) => {
                e.stopPropagation()
                deleteConversation(conv.id)
              }}
              className="ml-1 hidden shrink-0 rounded p-1 text-gray-400 hover:text-red-400 group-hover:block"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}

        {conversations.length === 0 && (
          <p className="mt-8 text-center text-xs text-gray-500">
            暂无对话记录
          </p>
        )}
      </nav>

      {/* 同步 Schema */}
      <div className="border-t border-gray-700 p-3">
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex w-full items-center gap-2 rounded-lg px-4 py-2 text-xs text-gray-400 hover:bg-[var(--color-sidebar-hover)] hover:text-gray-200 disabled:opacity-40"
        >
          <DatabaseZap size={16} className={syncing ? 'animate-spin' : ''} />
          {syncing ? '同步中...' : '同步 Schema'}
        </button>
      </div>
    </aside>
  )
}
