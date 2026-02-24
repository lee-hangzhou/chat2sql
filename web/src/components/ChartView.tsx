import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart, ScatterChart, FunnelChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  FunnelChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer,
])

interface Props {
  option: Record<string, unknown>
}

export default function ChartView({ option }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = echarts.init(containerRef.current)
    chartRef.current = chart
    chart.setOption(option as echarts.EChartsOption)

    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)

    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
      chartRef.current = null
    }
  }, [option])

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg border border-gray-200 bg-white"
      style={{ height: 400 }}
    />
  )
}
