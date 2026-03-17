/**
 * AccumulationChart — Gráfico de acúmulo de OBs na memória
 * Design: Terminal Quant — área chart mostrando crescimento
 */
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";

interface AccumulationData {
  candle: number;
  total: number;
  active: number;
  mitigated: number;
}

interface AccumulationChartProps {
  data: AccumulationData[];
}

export function AccumulationChart({ data }: AccumulationChartProps) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ff5252" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#ff5252" stopOpacity={0.05} />
          </linearGradient>
          <linearGradient id="colorActive" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#00e676" stopOpacity={0.4} />
            <stop offset="95%" stopColor="#00e676" stopOpacity={0.05} />
          </linearGradient>
          <linearGradient id="colorMitigated" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ff5252" stopOpacity={0.5} />
            <stop offset="95%" stopColor="#ff5252" stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
        <XAxis
          dataKey="candle"
          tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}
          axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
          tickLine={{ stroke: "rgba(255,255,255,0.05)" }}
        />
        <YAxis
          tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}
          axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
          tickLine={{ stroke: "rgba(255,255,255,0.05)" }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#0a0a14",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: "4px",
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: "11px",
            color: "#e0e0e0",
          }}
          labelFormatter={(v) => `Candle ${v}`}
        />
        <Legend
          wrapperStyle={{ fontSize: "10px", fontFamily: "'JetBrains Mono', monospace" }}
        />
        <Area
          type="stepAfter"
          dataKey="total"
          name="Total na Memória"
          stroke="#ff5252"
          fill="url(#colorTotal)"
          strokeWidth={1.5}
        />
        <Area
          type="stepAfter"
          dataKey="mitigated"
          name="Mitigados (Lixo)"
          stroke="#ff5252"
          fill="url(#colorMitigated)"
          strokeWidth={1}
          strokeDasharray="4 2"
        />
        <Area
          type="stepAfter"
          dataKey="active"
          name="Ativos (Úteis)"
          stroke="#00e676"
          fill="url(#colorActive)"
          strokeWidth={1.5}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
