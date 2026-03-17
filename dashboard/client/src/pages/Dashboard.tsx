/**
 * Dashboard — SMC Order Block Dashboard
 * Design: Terminal Quant — Bloomberg-inspired, dense data layout
 */
import { useMemo } from "react";
import { KpiCard } from "@/components/KpiCard";
import { CandlestickChart } from "@/components/CandlestickChart";
import { OrderBlocksTable } from "@/components/OrderBlocksTable";
import { TradesTable } from "@/components/TradesTable";
import { AccumulationChart } from "@/components/AccumulationChart";
import { EngineConfig } from "@/components/EngineConfig";
import TradeValidation from "@/components/TradeValidation";
import backtestDataRaw from "@/data/backtest-data.json";

const backtestData = backtestDataRaw as any;

import {
  Activity,
  TrendingUp,
  TrendingDown,
  Target,
  AlertTriangle,
  BarChart3,
  Layers,
  Zap,
  Database,
  Clock,
  Shield,
  Crosshair,
  Gauge,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

export default function Dashboard() {
  const data = useMemo(() => backtestData, []);
  const { stats, engine_config } = data;

  const expectedValue = useMemo(() => {
    if (stats.total_trades === 0) return 0;
    const wr = stats.win_rate / 100;
    const rr = stats.risk_reward_ratio;
    return (wr * rr) - ((1 - wr) * 1);
  }, [stats]);

  const breakEvenWinRate = useMemo(() => {
    const rr = stats.risk_reward_ratio;
    return (1 / (1 + rr)) * 100;
  }, [stats]);

  // OB distribution data
  const obDistribution = useMemo(() => {
    const bullish = data.order_blocks.filter((ob: any) => ob.direction === "bullish").length;
    const bearish = data.order_blocks.filter((ob: any) => ob.direction === "bearish").length;
    return [
      { name: "Bullish", value: bullish, color: "#00e676" },
      { name: "Bearish", value: bearish, color: "#ff9100" },
    ];
  }, [data]);

  // OB status data
  const obStatusData = useMemo(() => [
    { name: "Ativos", value: stats.active_obs, color: "#00e676" },
    { name: "Mitigados", value: stats.mitigated_obs, color: "#ff5252" },
  ], [stats]);

  // OB size distribution
  const obSizeData = useMemo(() => {
    return data.order_blocks.map((ob: any) => ({
      name: `#${ob.id}`,
      size: ob.ob_size,
      fill: ob.mitigated ? "#ff525260" : (ob.direction === "bullish" ? "#00e676" : "#ff9100"),
    }));
  }, [data]);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[1800px] mx-auto px-4 py-2 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-[#00e676] animate-pulse" />
              <h1 className="text-sm font-bold tracking-tight font-sans">SMC ORDER BLOCK DASHBOARD</h1>
            </div>
            <span className="text-[10px] font-mono text-muted-foreground px-2 py-0.5 bg-secondary rounded-sm">
              ENGINE V3
            </span>
            <span className="text-[10px] font-mono text-muted-foreground px-2 py-0.5 bg-secondary rounded-sm">
              {engine_config.symbol}
            </span>
          </div>
          <div className="flex items-center gap-4 text-[10px] font-mono text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {stats.candles_processed} candles
            </span>
            <span className="flex items-center gap-1">
              <Database className="w-3 h-3" />
              {stats.total_obs_in_memory} OBs na memória
            </span>
            <span className="flex items-center gap-1 text-[#ff5252]">
              <AlertTriangle className="w-3 h-3" />
              {stats.memory_waste_pct}% lixo
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-[1800px] mx-auto px-4 py-3 space-y-3">

        {/* === SEÇÃO 1: Assertividade 3:1 === */}
        <section className="bg-card border border-border/50 rounded-sm overflow-hidden">
          <div className="px-3 py-1.5 border-b border-border/30 flex items-center gap-2">
            <Target className="w-3.5 h-3.5 text-[#ffd700]" />
            <h2 className="text-[11px] font-semibold uppercase tracking-wider">
              Assertividade do Sistema 3:1
            </h2>
          </div>
          <div className="p-3">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
              <KpiCard
                label="Win Rate"
                value={`${stats.win_rate}%`}
                subtitle={`Break-Even: ${breakEvenWinRate.toFixed(0)}%`}
                trend={stats.win_rate > breakEvenWinRate ? "up" : "down"}
                icon={<Crosshair className="w-3.5 h-3.5" />}
              />
              <KpiCard
                label="Profit Factor"
                value={stats.profit_factor >= 999 ? "∞" : stats.profit_factor.toFixed(2)}
                subtitle="Lucro bruto / Perda bruta"
                trend={stats.profit_factor > 1.5 ? "up" : stats.profit_factor < 1 ? "down" : "neutral"}
                icon={<BarChart3 className="w-3.5 h-3.5" />}
              />
              <KpiCard
                label="Expectativa (R)"
                value={`${expectedValue >= 0 ? "+" : ""}${expectedValue.toFixed(2)}R`}
                subtitle="Ganho esperado por trade"
                trend={expectedValue > 0 ? "up" : "down"}
                icon={<Zap className="w-3.5 h-3.5" />}
              />
              <KpiCard
                label="Total P&L"
                value={`${stats.total_pnl >= 0 ? "+" : ""}${stats.total_pnl.toFixed(0)} pts`}
                subtitle={`${stats.total_pnl_r >= 0 ? "+" : ""}${stats.total_pnl_r.toFixed(1)}R total`}
                trend={stats.total_pnl > 0 ? "up" : "down"}
                icon={<Activity className="w-3.5 h-3.5" />}
              />
              <KpiCard
                label="Trades"
                value={stats.total_trades}
                subtitle={`${stats.wins}W / ${stats.losses}L`}
                trend="neutral"
                icon={<Layers className="w-3.5 h-3.5" />}
              />
              <KpiCard
                label="Risk:Reward"
                value={`1:${stats.risk_reward_ratio}`}
                subtitle={`Avg Win: ${stats.avg_win.toFixed(0)} pts`}
                trend="neutral"
                icon={<Shield className="w-3.5 h-3.5" />}
              />
            </div>

            {/* Assertividade visual explanation */}
            <div className="mt-3 grid grid-cols-1 lg:grid-cols-3 gap-3">
              {/* Win Rate gauge */}
              <div className="bg-secondary/30 rounded-sm p-3 border border-border/20">
                <h4 className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-2">
                  Win Rate vs Break-Even
                </h4>
                <div className="flex items-center gap-3">
                  <div className="relative w-16 h-16">
                    <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke="rgba(255,255,255,0.05)"
                        strokeWidth="3"
                      />
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke="#00e676"
                        strokeWidth="3"
                        strokeDasharray={`${stats.win_rate}, 100`}
                        strokeLinecap="round"
                      />
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke="#ffd700"
                        strokeWidth="1"
                        strokeDasharray={`${breakEvenWinRate}, 100`}
                        strokeLinecap="round"
                        opacity="0.5"
                      />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-[11px] font-mono font-bold text-[#00e676]">
                      {stats.win_rate}%
                    </span>
                  </div>
                  <div className="text-[10px] font-mono space-y-1">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-0.5 bg-[#00e676] rounded-full" />
                      <span className="text-muted-foreground">Win Rate Atual: <span className="text-[#00e676] font-semibold">{stats.win_rate}%</span></span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-0.5 bg-[#ffd700] rounded-full opacity-50" />
                      <span className="text-muted-foreground">Break-Even 3:1: <span className="text-[#ffd700] font-semibold">{breakEvenWinRate.toFixed(0)}%</span></span>
                    </div>
                    <div className="text-muted-foreground/70 mt-1">
                      {stats.win_rate > breakEvenWinRate
                        ? `Acima do BE por ${(stats.win_rate - breakEvenWinRate).toFixed(0)}pp`
                        : `Abaixo do BE por ${(breakEvenWinRate - stats.win_rate).toFixed(0)}pp`
                      }
                    </div>
                  </div>
                </div>
              </div>

              {/* OB Distribution */}
              <div className="bg-secondary/30 rounded-sm p-3 border border-border/20">
                <h4 className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-2">
                  Distribuição dos Order Blocks
                </h4>
                <div className="flex items-center gap-3">
                  <div className="w-16 h-16">
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie
                          data={obDistribution}
                          cx="50%"
                          cy="50%"
                          innerRadius={18}
                          outerRadius={28}
                          paddingAngle={3}
                          dataKey="value"
                          strokeWidth={0}
                        >
                          {obDistribution.map((entry: any, index: number) => (
                            <Cell key={index} fill={entry.color} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="text-[10px] font-mono space-y-1">
                    {obDistribution.map((d: any) => (
                      <div key={d.name} className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
                        <span className="text-muted-foreground">{d.name}: <span className="text-foreground font-semibold">{d.value}</span></span>
                      </div>
                    ))}
                    <div className="text-muted-foreground/70 mt-1">
                      Total: {data.order_blocks.length} OBs detectados
                    </div>
                  </div>
                </div>
              </div>

              {/* OB Status */}
              <div className="bg-secondary/30 rounded-sm p-3 border border-border/20">
                <h4 className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-2">
                  Status dos Order Blocks
                </h4>
                <div className="flex items-center gap-3">
                  <div className="w-16 h-16">
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie
                          data={obStatusData}
                          cx="50%"
                          cy="50%"
                          innerRadius={18}
                          outerRadius={28}
                          paddingAngle={3}
                          dataKey="value"
                          strokeWidth={0}
                        >
                          {obStatusData.map((entry: any, index: number) => (
                            <Cell key={index} fill={entry.color} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="text-[10px] font-mono space-y-1">
                    {obStatusData.map((d: any) => (
                      <div key={d.name} className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
                        <span className="text-muted-foreground">{d.name}: <span className="text-foreground font-semibold">{d.value}</span></span>
                      </div>
                    ))}
                    <div className="text-[#ff5252]/70 mt-1 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      {stats.memory_waste_pct}% da memória é lixo
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* === SEÇÃO 2: Gráfico de Preço === */}
        <section className="bg-card border border-border/50 rounded-sm overflow-hidden">
          <div className="px-3 py-1.5 border-b border-border/30 flex items-center justify-between">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-[#00e676]" />
              Gráfico de Preço + Order Blocks + Trades
            </h3>
            <span className="text-[10px] font-mono text-muted-foreground">
              {data.candles[0]?.time} — {data.candles[data.candles.length - 1]?.time}
            </span>
          </div>
          <div className="h-[450px]">
            <CandlestickChart
              candles={data.candles}
              orderBlocks={data.order_blocks}
              trades={data.trades}
              pendingOrders={data.pending_orders}
              swingHighs={data.swing_highs}
              swingLows={data.swing_lows}
            />
          </div>
        </section>

        {/* === SEÇÃO 3: Validação de Entrada/Saída === */}
        <section className="bg-card border border-border/50 rounded-sm overflow-hidden">
          <div className="px-3 py-1.5 border-b border-border/30 flex items-center justify-between">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-[#00e676]" />
              Validacao de Entrada/Saida (10 Checks por Trade)
            </h3>
            <span className={`text-[10px] font-mono font-bold ${
              stats.validation_checks_passed === stats.validation_checks_total
                ? "text-[#00e676]"
                : "text-[#ff5252]"
            }`}>
              {stats.validation_checks_passed}/{stats.validation_checks_total} checks
            </span>
          </div>
          <div className="p-3">
            <TradeValidation
              validations={data.trade_validations || []}
              stats={{
                validation_passed: stats.validation_passed || 0,
                validation_total: stats.validation_total || 0,
                validation_checks_passed: stats.validation_checks_passed || 0,
                validation_checks_total: stats.validation_checks_total || 0,
              }}
            />
          </div>
        </section>

        {/* === SEÇÃO 4: OB Table + Trades === */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <section className="bg-card border border-border/50 rounded-sm">
            <div className="px-3 py-1.5 border-b border-border/30 flex items-center justify-between">
              <h3 className="text-[11px] font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-[#ff9100]" />
                Order Blocks ({data.order_blocks.length})
              </h3>
              <div className="flex gap-2 text-[10px] font-mono">
                <span className="text-[#00e676]">{stats.active_obs} ativos</span>
                <span className="text-[#ff5252]">{stats.mitigated_obs} mitigados</span>
              </div>
            </div>
            <OrderBlocksTable orderBlocks={data.order_blocks} />
          </section>

          <section className="bg-card border border-border/50 rounded-sm">
            <div className="px-3 py-1.5 border-b border-border/30 flex items-center justify-between">
              <h3 className="text-[11px] font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5 text-[#ffd700]" />
                Trades + Ordens Pendentes
              </h3>
              <span className="text-[10px] font-mono text-muted-foreground">
                {data.trades.length} fechados | {data.pending_orders.length} pendentes
              </span>
            </div>
            <TradesTable trades={data.trades} pendingOrders={data.pending_orders} />
          </section>
        </div>

        {/* === SEÇÃO 5: Acúmulo + OB Sizes + Config === */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
          {/* Accumulation Chart */}
          <section className="lg:col-span-5 bg-card border border-border/50 rounded-sm">
            <div className="px-3 py-1.5 border-b border-border/30 flex items-center justify-between">
              <h3 className="text-[11px] font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-[#ff5252]" />
                Acúmulo de OBs (Memory Leak)
              </h3>
              <span className="text-[10px] font-mono text-[#ff5252]">
                {stats.memory_waste_pct}% lixo
              </span>
            </div>
            <div className="h-[200px] p-2">
              <AccumulationChart data={data.ob_accumulation} />
            </div>
          </section>

          {/* OB Size Distribution */}
          <section className="lg:col-span-3 bg-card border border-border/50 rounded-sm">
            <div className="px-3 py-1.5 border-b border-border/30">
              <h3 className="text-[11px] font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <Gauge className="w-3.5 h-3.5 text-[#40c4ff]" />
                Tamanho dos OBs (pts)
              </h3>
            </div>
            <div className="h-[200px] p-2">
              <ResponsiveContainer>
                <BarChart data={obSizeData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                  <XAxis
                    dataKey="name"
                    tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                  />
                  <YAxis
                    tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
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
                    formatter={(value: any) => [`${value} pts`, "Tamanho"]}
                  />
                  <Bar dataKey="size" radius={[2, 2, 0, 0]}>
                    {obSizeData.map((entry: any, index: number) => (
                      <Cell key={index} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          {/* Engine Config + Diagnostics */}
          <section className="lg:col-span-4 bg-card border border-border/50 rounded-sm">
            <div className="px-3 py-1.5 border-b border-border/30">
              <h3 className="text-[11px] font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-[#ffd700]" />
                Engine Config + Diagnóstico
              </h3>
            </div>
            <div className="p-3">
              <EngineConfig config={engine_config} />
              <div className="mt-3 space-y-1.5">
                <h4 className="text-[9px] font-medium uppercase tracking-wider text-muted-foreground">
                  Problemas Detectados
                </h4>
                <DiagnosticItem severity="low" text={`GC ativo: ${stats.mitigated_obs} OBs mitigados limpos (${stats.memory_waste_pct}% lixo)`} />
                <DiagnosticItem severity="low" text="Sinais repetidos corrigidos (1 sinal por OB)" />
                <DiagnosticItem severity="low" text="Swings limitados a 200 entradas" />
                <DiagnosticItem severity="low" text="V3 e Realtime alinhados (corpo do candle)" />
                <DiagnosticItem severity="low" text="Filtro de OBs duplicados (>50% overlap)" />
                <DiagnosticItem severity="low" text="Expiração de ordens: 100 candles (Realtime)" />
              </div>
            </div>
          </section>
        </div>

        {/* Footer */}
        <footer className="text-center text-[10px] font-mono text-muted-foreground py-4 border-t border-border/30">
          SMC Engine V3 Audit Dashboard — {engine_config.symbol} M1 — {stats.candles_processed} candles — RR 1:{stats.risk_reward_ratio}
        </footer>
      </main>
    </div>
  );
}

function DiagnosticItem({ severity, text }: { severity: "critical" | "high" | "medium" | "low"; text: string }) {
  const colors = {
    critical: "bg-[#ff3b3b]/10 text-[#ff3b3b] border-[#ff3b3b]/20",
    high: "bg-[#ff9100]/10 text-[#ff9100] border-[#ff9100]/20",
    medium: "bg-[#ffd700]/10 text-[#ffd700] border-[#ffd700]/20",
    low: "bg-[#40c4ff]/10 text-[#40c4ff] border-[#40c4ff]/20",
  };
  const labels = {
    critical: "CRIT",
    high: "ALTO",
    medium: "MED",
    low: "BAIXO",
  };

  return (
    <div className={`flex items-start gap-1.5 text-[9px] font-mono px-2 py-1 rounded-sm border ${colors[severity]}`}>
      <span className="font-bold shrink-0">[{labels[severity]}]</span>
      <span className="opacity-90 leading-tight">{text}</span>
    </div>
  );
}
