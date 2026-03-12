import type { ResponseType } from '../types'

interface CanvasToolbarProps {
  title: string
  responseType: ResponseType | null
  hasData: boolean
  onSwitchChart: () => void
  onRequestInsight: () => void
  onExportCSV: () => void
}

export default function CanvasToolbar({
  title,
  responseType,
  hasData,
  onSwitchChart,
  onRequestInsight,
  onExportCSV,
}: CanvasToolbarProps) {
  if (!title && !hasData) return null

  const isQueryOrChart = hasData && (responseType === 'query' || responseType === 'chart_update')
  const isInsight = hasData && responseType === 'insight'

  return (
    <div className="flex h-12 shrink-0 items-center justify-between border-b border-gray-200 px-4">
      {/* 左侧标题 */}
      <span
        className="max-w-[60%] truncate text-sm font-medium text-gray-700"
        title={title}
      >
        {title}
      </span>

      {/* 右侧按钮组 */}
      <div className="flex items-center gap-1.5">
        {isQueryOrChart && (
          <>
            <button
              onClick={onSwitchChart}
              className="flex items-center gap-1 rounded-lg border border-gray-300 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-50 hover:border-gray-400"
            >
              <span>📊</span>
              换图表
            </button>
            <button
              onClick={onRequestInsight}
              className="flex items-center gap-1 rounded-lg border border-gray-300 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-50 hover:border-gray-400"
            >
              <span>🔍</span>
              深度分析
            </button>
            <button
              onClick={onExportCSV}
              className="flex items-center gap-1 rounded-lg border border-gray-300 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-50 hover:border-gray-400"
            >
              <span>↓</span>
              导出 CSV
            </button>
          </>
        )}

        {isInsight && (
          <button
            onClick={onExportCSV}
            className="flex items-center gap-1 rounded-lg border border-gray-300 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-50 hover:border-gray-400"
          >
            <span>↓</span>
            导出报告
          </button>
        )}
      </div>
    </div>
  )
}
