"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  Time,
  ColorType,
} from "lightweight-charts";

export interface OHLCData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface TradingChartProps {
  data: OHLCData[];
  height?: number;
  symbol?: string;
}

export function TradingChart({ data, height = 400, symbol }: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

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

    const series = chart.addCandlestickSeries({
      upColor: "#00FF88",
      downColor: "#FF4444",
      borderUpColor: "#00FF88",
      borderDownColor: "#FF4444",
      wickUpColor: "#00FF88",
      wickDownColor: "#FF4444",
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

    const candleData: CandlestickData<Time>[] = data.map((d) => ({
      time: (d.time as unknown) as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    seriesRef.current.setData(candleData);
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return (
    <div className="bg-brand-surface border border-brand-border rounded-xl overflow-hidden">
      {symbol && (
        <div className="px-4 py-2 border-b border-brand-border">
          <span className="text-sm font-mono font-medium">{symbol}</span>
        </div>
      )}
      <div ref={containerRef} className="w-full" />
    </div>
  );
}
