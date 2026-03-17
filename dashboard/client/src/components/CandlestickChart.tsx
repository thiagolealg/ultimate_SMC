/**
 * CandlestickChart — Lightweight Charts v5 com Order Blocks overlay
 * Design: Terminal Quant — fundo escuro, OBs como price lines
 */
import { useEffect, useRef, useCallback } from "react";
import {
  createChart,
  CandlestickSeries,
  ColorType,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";

interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface OrderBlock {
  id: number;
  direction: "bullish" | "bearish";
  top: number;
  bottom: number;
  midline: number;
  ob_candle_index: number;
  confirmation_index: number;
  mitigated: boolean;
  mitigated_index: number | null;
  used: boolean;
  volume_ratio: number;
  ob_size: number;
  ob_size_atr: number;
}

interface Trade {
  id: string;
  direction: "bullish" | "bearish";
  entry_price: number;
  exit_price: number;
  sl: number;
  tp: number;
  pnl: number;
  pnl_r: number;
  status: string;
  filled_at: number;
  closed_at: number;
  ob_id: number;
}

interface PendingOrder {
  id: string;
  direction: "bullish" | "bearish";
  entry_price: number;
  sl: number;
  tp: number;
  ob_id: number;
  created_at: number;
}

interface SwingPoint {
  conf_idx: number;
  candle_idx: number;
  level: number;
}

interface CandlestickChartProps {
  candles: Candle[];
  orderBlocks: OrderBlock[];
  trades: Trade[];
  pendingOrders: PendingOrder[];
  swingHighs: SwingPoint[];
  swingLows: SwingPoint[];
}

export function CandlestickChart({
  candles,
  orderBlocks,
  trades,
  pendingOrders,
  swingHighs,
  swingLows,
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const initChart = useCallback(() => {
    if (!containerRef.current) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0a0a14" },
        textColor: "#8b8fa3",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.03)" },
        horzLines: { color: "rgba(255,255,255,0.03)" },
      },
      crosshair: {
        vertLine: { color: "rgba(0,255,136,0.3)", width: 1, style: 2, labelBackgroundColor: "#1a1a2e" },
        horzLine: { color: "rgba(0,255,136,0.3)", width: 1, style: 2, labelBackgroundColor: "#1a1a2e" },
      },
      rightPriceScale: {
        borderColor: "rgba(255,255,255,0.1)",
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: "rgba(255,255,255,0.1)",
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // v5 API: addSeries(CandlestickSeries, options)
    const candleSeries: ISeriesApi<"Candlestick"> = chart.addSeries(CandlestickSeries, {
      upColor: "#00e676",
      downColor: "#ff3b3b",
      borderUpColor: "#00e676",
      borderDownColor: "#ff3b3b",
      wickUpColor: "#00e67688",
      wickDownColor: "#ff3b3b88",
    });

    // Use numeric index as time (WhitespaceData)
    const candleData = candles.map((c, i) => ({
      time: (i + 1) as unknown as import("lightweight-charts").Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    candleSeries.setData(candleData);

    // Markers
    const markers: any[] = [];

    swingHighs.forEach((sh) => {
      if (sh.candle_idx >= 0 && sh.candle_idx < candles.length) {
        markers.push({
          time: (sh.candle_idx + 1) as any,
          position: "aboveBar",
          color: "#ff4081",
          shape: "arrowDown",
          text: "SH",
        });
      }
    });

    swingLows.forEach((sl) => {
      if (sl.candle_idx >= 0 && sl.candle_idx < candles.length) {
        markers.push({
          time: (sl.candle_idx + 1) as any,
          position: "belowBar",
          color: "#40c4ff",
          shape: "arrowUp",
          text: "SL",
        });
      }
    });

    trades.forEach((t) => {
      if (t.filled_at >= 0 && t.filled_at < candles.length) {
        markers.push({
          time: (t.filled_at + 1) as any,
          position: t.direction === "bullish" ? "belowBar" : "aboveBar",
          color: "#ffd700",
          shape: "circle",
          text: `ENTRY`,
        });
      }
      if (t.closed_at >= 0 && t.closed_at < candles.length) {
        markers.push({
          time: (t.closed_at + 1) as any,
          position: t.direction === "bullish" ? "aboveBar" : "belowBar",
          color: t.pnl > 0 ? "#00e676" : "#ff3b3b",
          shape: "square",
          text: t.pnl > 0 ? "TP" : "SL",
        });
      }
    });

    markers.sort((a: any, b: any) => (a.time as number) - (b.time as number));
    createSeriesMarkers(candleSeries, markers);

    // OB price lines
    orderBlocks.forEach((ob) => {
      const isActive = !ob.mitigated;
      const isBullish = ob.direction === "bullish";

      const color = isActive
        ? (isBullish ? "rgba(0,230,118,0.4)" : "rgba(255,145,0,0.4)")
        : "rgba(255,82,82,0.15)";

      candleSeries.createPriceLine({
        price: ob.top,
        color,
        lineWidth: 1,
        lineStyle: isActive ? 0 : 2,
        axisLabelVisible: false,
        title: `OB#${ob.id} ${isBullish ? "BULL" : "BEAR"} ${isActive ? "" : "MIT"} ▲`,
      });

      candleSeries.createPriceLine({
        price: ob.bottom,
        color,
        lineWidth: 1,
        lineStyle: isActive ? 0 : 2,
        axisLabelVisible: false,
        title: "",
      });

      candleSeries.createPriceLine({
        price: ob.midline,
        color: isActive
          ? (isBullish ? "rgba(0,230,118,0.2)" : "rgba(255,145,0,0.2)")
          : "rgba(255,82,82,0.08)",
        lineWidth: 1,
        lineStyle: 1,
        axisLabelVisible: isActive,
        title: isActive ? `OB#${ob.id}` : "",
      });
    });

    // Pending order lines
    pendingOrders.forEach((po) => {
      candleSeries.createPriceLine({
        price: po.entry_price,
        color: "rgba(255,235,59,0.6)",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `PEND #${po.id.slice(-2)}`,
      });
      candleSeries.createPriceLine({
        price: po.sl,
        color: "rgba(255,59,59,0.25)",
        lineWidth: 1,
        lineStyle: 3,
        axisLabelVisible: false,
        title: "",
      });
      candleSeries.createPriceLine({
        price: po.tp,
        color: "rgba(0,230,118,0.25)",
        lineWidth: 1,
        lineStyle: 3,
        axisLabelVisible: false,
        title: "",
      });
    });

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chart.applyOptions({ width, height });
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [candles, orderBlocks, trades, pendingOrders, swingHighs, swingLows]);

  useEffect(() => {
    const cleanup = initChart();
    return cleanup;
  }, [initChart]);

  return (
    <div className="w-full h-full relative">
      <div ref={containerRef} className="w-full h-full" />
      <div className="absolute top-2 left-2 flex gap-3 text-[10px] font-mono bg-[#0a0a14]/80 backdrop-blur-sm px-2 py-1 rounded-sm border border-border/30">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-[#00e676]" /> OB Bull Ativo
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-[#ff9100]" /> OB Bear Ativo
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-[#ff5252] opacity-50" /> Mitigado
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-[#ffd700]" /> Pendente
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-[#ff4081]" /> Swing H
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-[#40c4ff]" /> Swing L
        </span>
      </div>
    </div>
  );
}
