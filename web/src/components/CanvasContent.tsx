import type { CanvasState, InsightFinding } from '../types'
import ChartView from './ChartView'
import ResultTable from './ResultTable'

interface CanvasContentProps {
  canvasState: CanvasState
}

const EXAMPLE_QUESTIONS = [
  '最近30天的任务完成趋势',
  '各剧集任务数量对比',
  '找出任务数量异常的剧集',
]

const SEVERITY_COLOR: Record<InsightFinding['severity'], string> = {
  high: '#ef4444',
  medium: '#f59e0b',
  low: '#3b82f6',
}

function suggestInput(text: string) {
  window.dispatchEvent(new CustomEvent('suggest-input', { detail: text }))
}

/* ── Skeleton ─────────────────────────────────────────────────────────── */
function Skeleton() {
  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <div className="animate-pulse rounded-lg bg-gray-200" style={{ flex: '3' }} />
      <div className="flex flex-col gap-2" style={{ flex: '2' }}>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-6 animate-pulse rounded bg-gray-200" />
        ))}
      </div>
    </div>
  )
}

/* ── Empty state ──────────────────────────────────────────────────────── */
function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 px-8 text-center">
      <span className="text-6xl">📊</span>
      <div className="space-y-1">
        <p className="text-base font-medium text-gray-700">输入问题，开始分析数据</p>
        <p className="text-sm text-gray-400">试试下面的示例</p>
      </div>
      <div className="flex w-full max-w-md flex-col gap-2">
        {EXAMPLE_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => suggestInput(q)}
            className="rounded-lg border border-gray-200 px-4 py-2.5 text-left text-sm text-gray-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 transition-colors"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}

/* ── Summary card ─────────────────────────────────────────────────────── */
function SummaryCard({ text }: { text: string }) {
  return (
    <div className="flex h-full flex-col gap-1.5 overflow-y-auto rounded-lg border border-gray-200 bg-gray-50 p-3">
      <span className="inline-flex w-fit rounded bg-blue-100 px-1.5 py-0.5 text-[11px] font-medium text-blue-700">
        AI 总结
      </span>
      <p
        className="flex-1 text-gray-500"
        style={{ fontSize: 13, lineHeight: 1.7 }}
      >
        {text || '—'}
      </p>
    </div>
  )
}

/* ── Insight report panel ─────────────────────────────────────────────── */
function InsightPanel({ canvasState }: { canvasState: CanvasState }) {
  const report = canvasState.insightReport
  if (!report) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400">
        暂无洞察报告
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto">
      {/* Summary */}
      {report.summary && (
        <div className="rounded-lg bg-green-50 p-3 text-sm text-green-800" style={{ lineHeight: 1.7 }}>
          {report.summary}
        </div>
      )}

      {/* Findings */}
      <div className="flex flex-col gap-2">
        {report.findings.map((finding, i) => (
          <div
            key={i}
            className="rounded-lg border border-gray-200 bg-white p-3"
            style={{ borderLeftWidth: 3, borderLeftColor: SEVERITY_COLOR[finding.severity] }}
          >
            <p className="text-sm font-semibold text-gray-800">{finding.conclusion}</p>
            {finding.chart_suggestion && (
              <span className="mt-1 inline-block rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500">
                建议图表：{finding.chart_suggestion}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Main component ───────────────────────────────────────────────────── */
export default function CanvasContent({ canvasState }: CanvasContentProps) {
  const { responseType, isLoading, chartOption, tableData, summaryText } = canvasState

  /* Loading */
  if (isLoading) return <Skeleton />

  /* Empty */
  if (responseType === null) return <EmptyState />

  /* Chat */
  if (responseType === 'chat') {
    return (
      <div className="flex h-full items-start justify-center overflow-y-auto px-8 py-10">
        <p
          className="max-w-2xl text-gray-700"
          style={{ fontSize: 15, lineHeight: 1.8 }}
        >
          {summaryText || '—'}
        </p>
      </div>
    )
  }

  /* Query / Chart update */
  if (responseType === 'query' || responseType === 'chart_update') {
    return (
      <div className="flex h-full flex-col overflow-y-auto p-4 gap-4">
        {/* Chart area */}
        <div style={{ minHeight: 200 }}>
          {chartOption ? (
            <ChartView option={chartOption as Record<string, unknown>} />
          ) : (
            <div className="flex min-h-[200px] items-center justify-center rounded-lg border border-dashed border-gray-300 text-sm text-gray-400">
              暂无图表
            </div>
          )}
        </div>

        {/* Data + summary area */}
        <div className="flex gap-3" style={{ minHeight: 200 }}>
          {/* ResultTable already includes CSV download */}
          <div className="overflow-auto" style={{ width: '55%' }}>
            {tableData && tableData.length > 0 ? (
              <ResultTable data={tableData as Record<string, unknown>[]} />
            ) : (
              <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-gray-300 text-sm text-gray-400">
                暂无数据
              </div>
            )}
          </div>

          <div style={{ width: '45%' }}>
            <SummaryCard text={summaryText} />
          </div>
        </div>
      </div>
    )
  }

  /* Insight */
  if (responseType === 'insight') {
    return (
      <div className="flex h-full overflow-hidden">
        {/* Left: chart + table */}
        <div className="flex flex-col gap-4 overflow-y-auto p-4" style={{ width: '55%' }}>
          {chartOption && (
            <ChartView option={chartOption as Record<string, unknown>} />
          )}
          {tableData && tableData.length > 0 && (
            <ResultTable data={tableData as Record<string, unknown>[]} />
          )}
          {!chartOption && (!tableData || tableData.length === 0) && (
            <div className="flex flex-1 items-center justify-center text-sm text-gray-400">
              暂无数据
            </div>
          )}
        </div>

        {/* Right: insight report */}
        <div
          className="overflow-y-auto border-l border-gray-200 p-4"
          style={{ width: '45%' }}
        >
          <InsightPanel canvasState={canvasState} />
        </div>
      </div>
    )
  }

  return null
}
