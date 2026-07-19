"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  AreaData,
  Time,
  ColorType,
  LineStyle,
} from "lightweight-charts";

export interface DrawdownData {
  date: string;
  drawdown: number;
}

interface DrawdownChartProps {
  data: DrawdownData[];
  height?: number;
}

export function DrawdownChart({ data, height = 400 }: DrawdownChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#161B22" },
        textColor: "#8B949E",
      },
      grid: {
        vertLines: { color: "#30363D" },
        horzLines: { color: "#30363D" },
      },
      crosshair: {
        mode: 0,
      },
      timeScale: {
        borderColor: "#30363D",
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: "#30363D",
      },
    });

    const series = chart.addAreaSeries({
      topColor: "rgba(255, 68, 68, 0.4)",
      bottomColor: "rgba(255, 68, 68, 0.0)",
      lineColor: "#FF4444",
      lineWidth: 2,
    });

    // Add zero line
    chart.addLineSeries({
      color: "#30363D",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [height]);

  useEffect(() => {
    if (!seriesRef.current || !data.length) return;

    const areaData: AreaData<Time>[] = data.map((d) => ({
      time: (d.date as unknown) as Time,
      value: -d.drawdown, // Negative so drawdowns show below zero
    }));

    seriesRef.current.setData(areaData);
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return (
    <div className="bg-brand-surface border border-brand-border rounded-xl overflow-hidden">
      <div className="px-4 py-2 border-b border-brand-border">
        <span className="text-sm font-mono font-medium">Drawdown</span>
      </div>
      <div ref={containerRef} className="w-full" />
    </div>
  );
}
