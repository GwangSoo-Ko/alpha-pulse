"use client"
import { useEffect, useRef } from "react"
import {
  createChart,
  ColorType,
  LineStyle,
  type IChartApi,
} from "lightweight-charts"
import type { Snapshot } from "@/lib/types"

export function EquityCurve({
  snapshots,
  initialCapital,
}: {
  snapshots: Snapshot[]
  initialCapital: number
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0a0a0a" },
        textColor: "#e5e5e5",
      },
      grid: {
        vertLines: { color: "#1f1f1f" },
        horzLines: { color: "#1f1f1f" },
      },
      height: 360,
    })
    chartRef.current = chart
    const series = chart.addLineSeries({ color: "#22c55e", lineWidth: 2 })
    const baseline = chart.addLineSeries({
      color: "#525252",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
    })
    const data = snapshots.map((s) => ({
      time: `${s.date.slice(0, 4)}-${s.date.slice(4, 6)}-${s.date.slice(6, 8)}` as `${number}-${number}-${number}`,
      value: s.total_value,
    }))
    series.setData(data)
    const baseData = data.map((d) => ({ time: d.time, value: initialCapital }))
    baseline.setData(baseData)
    chart.timeScale().fitContent()
    const resize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
        })
      }
    }
    resize()
    window.addEventListener("resize", resize)
    return () => {
      window.removeEventListener("resize", resize)
      chart.remove()
    }
  }, [snapshots, initialCapital])

  return <div ref={containerRef} className="w-full" />
}
