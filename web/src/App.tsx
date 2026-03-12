import { useEffect, useRef, useState } from 'react'
import { MessageSquare } from 'lucide-react'
import { useAuthStore } from './stores/auth'
import { useChatStore } from './stores/chat'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import MessageInput, { type MessageInputHandle } from './components/MessageInput'
import CanvasToolbar from './components/CanvasToolbar'
import CanvasContent from './components/CanvasContent'
import NodeProgress from './components/NodeProgress'

export default function App() {
  const { isAuthenticated, loading, restore } = useAuthStore()
  const { loadConversations, reset, canvasState, sendMessage, sending, nodeSteps } = useChatStore()

  const inputRef = useRef<MessageInputHandle>(null)
  const [isNarrow, setIsNarrow] = useState(() => window.innerWidth < 900)
  const [canvasVisible, setCanvasVisible] = useState(false)

  // 恢复登录态
  useEffect(() => {
    restore()
  }, [restore])

  // 登录/登出后加载或清空对话列表
  useEffect(() => {
    if (loading) return
    if (isAuthenticated) loadConversations()
    else reset()
  }, [isAuthenticated, loading, loadConversations, reset])

  // 监听 token 过期事件
  useEffect(() => {
    const handler = () => {
      const { isAuthenticated } = useAuthStore.getState()
      if (isAuthenticated) useAuthStore.getState().logout()
    }
    window.addEventListener('auth:expired', handler)
    return () => window.removeEventListener('auth:expired', handler)
  }, [])

  // 响应式宽度检测
  useEffect(() => {
    const onResize = () => setIsNarrow(window.innerWidth < 900)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // 监听 CanvasContent 示例问题点击派发的 suggest-input 事件
  useEffect(() => {
    const handler = (e: Event) => {
      inputRef.current?.fill((e as CustomEvent<string>).detail)
    }
    window.addEventListener('suggest-input', handler)
    return () => window.removeEventListener('suggest-input', handler)
  }, [])

  const handleRequestInsight = () => {
    inputRef.current?.fill('请对当前数据进行深度洞察分析')
  }

  const handleSwitchChart = () => {
    inputRef.current?.fill('换一种图表展示')
  }

  const handleExportCSV = () => {
    const { tableData, tableColumns } = canvasState
    if (!tableData || !tableColumns.length) return
    const header = tableColumns.join(',')
    const rows = tableData.map((row) =>
      tableColumns
        .map((col) => {
          const val = String(row[col] ?? '')
          return val.includes(',') || val.includes('"') || val.includes('\n')
            ? `"${val.replace(/"/g, '""')}"`
            : val
        })
        .join(',')
    )
    const csv = '\uFEFF' + [header, ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'result.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="flex h-full flex-col">
        <Header />
        <div className="flex flex-1 items-center justify-center text-gray-400">
          <div className="text-center">
            <MessageSquare size={48} className="mx-auto mb-4" />
            <p className="text-lg">请先登录</p>
          </div>
        </div>
      </div>
    )
  }

  const hasData = !!(canvasState.chartOption || canvasState.tableData?.length)

  return (
    <div className="flex h-full flex-col">
      <Header />

      <div className="relative flex flex-1 overflow-hidden">
        {/* ── 左侧栏 ──────────────────────────────────────────── */}
        <div className="flex w-64 shrink-0 flex-col" style={{ zIndex: 10 }}>
          {/* 对话列表（Sidebar 包含新建对话、历史列表、同步 Schema） */}
          <div className="min-h-0 flex-1 overflow-hidden">
            <Sidebar />
          </div>

          {/* 输入区 */}
          <div className="shrink-0">
            <MessageInput
              ref={inputRef}
              onSend={sendMessage}
              disabled={sending}
              placeholder={sending ? '正在处理中...' : '输入你的问题...'}
            />
          </div>

          {/* 窄屏：查看结果按钮 */}
          {isNarrow && (
            <div className="shrink-0 border-t border-gray-700 bg-[var(--color-sidebar)] p-2">
              <button
                onClick={() => setCanvasVisible(true)}
                className="w-full rounded-lg border border-gray-600 px-3 py-2 text-sm text-gray-300 hover:bg-[var(--color-sidebar-hover)]"
              >
                查看结果 →
              </button>
            </div>
          )}
        </div>

        {/* ── 右侧画布 ─────────────────────────────────────────── */}
        <div
          className={[
            'flex flex-1 flex-col overflow-hidden bg-white',
            isNarrow ? 'absolute inset-0 z-20 transition-transform duration-300' : '',
            isNarrow ? (canvasVisible ? 'translate-x-0' : 'translate-x-full') : '',
          ]
            .filter(Boolean)
            .join(' ')}
        >
          {/* 窄屏：返回按钮 */}
          {isNarrow && canvasVisible && (
            <div className="shrink-0 border-b border-gray-200 px-4 py-2">
              <button
                onClick={() => setCanvasVisible(false)}
                className="text-sm text-blue-600 hover:text-blue-700"
              >
                ← 返回
              </button>
            </div>
          )}

          <CanvasToolbar
            title={canvasState.queryTitle}
            responseType={canvasState.responseType}
            hasData={hasData}
            onSwitchChart={handleSwitchChart}
            onRequestInsight={handleRequestInsight}
            onExportCSV={handleExportCSV}
          />

          <div className="relative min-h-0 flex-1 overflow-hidden">
            <CanvasContent canvasState={canvasState} />

            {/* 节点执行进度面板：右侧滑入覆盖 */}
            {nodeSteps.length > 0 && (
              <div className="absolute bottom-0 right-0 top-0 z-10 w-56 overflow-y-auto border-l border-gray-200 bg-white p-4">
                <h3 className="mb-3 text-xs font-medium uppercase tracking-wide text-gray-500">
                  执行进度
                </h3>
                <NodeProgress steps={nodeSteps} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
