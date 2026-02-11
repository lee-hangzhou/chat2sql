interface Props {
  data: Record<string, unknown>[]
}

export default function ResultTable({ data }: Props) {
  if (!data.length) return null

  const columns = Object.keys(data[0])

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-gray-50 text-xs font-medium uppercase text-gray-600">
          <tr>
            {columns.map((col) => (
              <th key={col} className="px-4 py-2.5 whitespace-nowrap">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {data.map((row, i) => (
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
  )
}
