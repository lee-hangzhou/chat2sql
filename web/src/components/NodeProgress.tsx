import { useEffect, useState } from 'react'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import type { NodeStep } from '../types'

interface Props {
  steps: NodeStep[]
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function RunningTimer({ startTime }: { startTime: number }) {
  const [elapsed, setElapsed] = useState(Date.now() - startTime)

  useEffect(() => {
    const id = setInterval(() => setElapsed(Date.now() - startTime), 100)
    return () => clearInterval(id)
  }, [startTime])

  return <span className="text-xs text-blue-500">{formatMs(elapsed)}</span>
}

export default function NodeProgress({ steps }: Props) {
  if (steps.length === 0) return null

  return (
    <div className="space-y-0">
      {steps.map((step, i) => (
        <div key={`${step.node}-${i}`} className="flex items-start gap-3">
          {/* 竖线 + 图标 */}
          <div className="flex flex-col items-center">
            {step.status === 'completed' ? (
              <CheckCircle2 size={18} className="shrink-0 text-emerald-500" />
            ) : step.status === 'running' ? (
              <Loader2 size={18} className="shrink-0 animate-spin text-blue-500" />
            ) : (
              <XCircle size={18} className="shrink-0 text-red-500" />
            )}
            {i < steps.length - 1 && (
              <div className="w-px flex-1 bg-gray-200 min-h-[20px]" />
            )}
          </div>

          {/* 标签 + 耗时 */}
          <div className="flex items-center gap-2 pb-4">
            <span
              className={`text-sm ${
                step.status === 'running'
                  ? 'font-medium text-blue-600'
                  : step.status === 'completed'
                    ? 'text-gray-600'
                    : 'text-red-500'
              }`}
            >
              {step.label}
            </span>
            {step.status === 'running' && <RunningTimer startTime={step.startTime} />}
            {step.status !== 'running' && step.elapsedMs !== null && (
              <span className={`text-xs ${step.status === 'failed' ? 'text-red-400' : 'text-gray-400'}`}>
                {formatMs(step.elapsedMs)}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
