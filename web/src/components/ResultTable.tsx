import { useState } from 'react'
import { ChevronLeft, ChevronRight, Download } from 'lucide-react'

const PAGE_SIZE = 50

interface Props {
  data: Record<string, unknown>[]
}

export default function ResultTable({ data }: Props) {
  const [page, setPage] = useState(0)

  if (!data.length) return null

  const columns = Object.keys(data[0])
  const totalPages = Math.ceil(data.length / PAGE_SIZE)
  const pageData = data.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  const handleDownload = () => {
    const header = columns.join(',')
    const rows = data.map((row) =>
      columns.map((col) => {
        const val = String(row[col] ?? '')
        return val.includes(',') || val.includes('"') || val.includes('\n')
          ? `"${val.replace(/"/g, '""')}"`
          : val
      }).join(',')
    )
    const csv = [header, ...rows].join('\n')
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `query_result_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col gap-2">
      {/* 工具栏 */}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>查询结果（{data.length} 行）</span>
        <button
          onClick={handleDownload}
          className="flex items-center gap-1 rounded px-2 py-1 hover:bg-gray-100 hover:text-gray-700"
        >
          <Download size={14} />
          下载 CSV
        </button>
      </div>

      {/* 表格容器 */}
      <div className="max-h-[400px] overflow-auto rounded-lg border border-gray-200">
        <table className="min-w-full text-left text-sm">
          <thead className="sticky top-0 bg-gray-50 text-xs font-medium uppercase text-gray-600">
            <tr>
              {columns.map((col) => (
                <th key={col} className="px-4 py-2.5 whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {pageData.map((row, i) => (
              <tr key={i} className="hover:bg-gray-50">
                {columns.map((col) => (
                  <td key={col} className="px-4 py-2 whitespace-nowrap text-gray-700">
                    {String(row[col] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 text-xs text-gray-500">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded p-1 hover:bg-gray-100 disabled:opacity-30"
          >
            <ChevronLeft size={16} />
          </button>
          <span>
            {page + 1} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page === totalPages - 1}
            className="rounded p-1 hover:bg-gray-100 disabled:opacity-30"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  )
}
