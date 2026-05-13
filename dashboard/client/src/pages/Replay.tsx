/**
 * Replay — Market Replay com dados BTC online + SMC Trades
 * Mostra trades e Order Blocks aparecendo conforme os candles avançam
 */
import { useMemo } from "react";
import { CandlestickChart } from "@/components/CandlestickChart";
import { ReplayControls } from "@/components/ReplayControls";
import { useBTCData } from "@/hooks/useBTCData";
import { useReplay } from "@/hooks/useReplay";
import { Activity, Wifi, WifiOff, RefreshCw, TrendingUp, TrendingDown, Target } from "lucide-react";
import backtestDataRaw from "@/data/backtest-data.json";

const backtestData = backtestDataRaw as any;

export default function Replay() {
  const { candles, loading, error, refetch } = useBTCData({
    symbol: "BTCUSDT",
    interval: "5m",
    limit: 500,
  });

  const {
    currentIndex,
    isPlaying,
    speed,
    play,
    pause,
    reset,
    stepForward,
    seek,
    changeSpeed,
  } = useReplay({ totalCandles: candles.length, initialVisible: 20 });

  // Slice candles up to currentIndex for replay effect
  const visibleCandles = useMemo(
    () => candles.slice(0, currentIndex),
    [candles, currentIndex]
  );

  // Filter trades that have been filled within visible range
  const visibleTrades = useMemo(() => {
    return (backtestData.trades || []).filter(
      (t: any) => t.filled_at < currentIndex && t.closed_at < currentIndex
    );
  }, [currentIndex]);

  // Filter order blocks that have been confirmed within visible range
  const visibleOrderBlocks = useMemo(() => {
    return (backtestData.order_blocks || []).filter(
      (ob: any) => ob.confirmation_index < currentIndex
    );
  }, [currentIndex]);

  // Filter swing points within visible range
  const visibleSwingHighs = useMemo(() => {
    return (backtestData.swing_highs || []).filter(
      (sh: any) => sh.candle_idx < currentIndex
    );
  }, [currentIndex]);

  const visibleSwingLows = useMemo(() => {
    return (backtestData.swing_lows || []).filter(
      (sl: any) => sl.candle_idx < currentIndex
    );
  }, [currentIndex]);

  // Pending orders visible
  const visiblePendingOrders = useMemo(() => {
    return (backtestData.pending_orders || []).filter(
      (po: any) => po.created_at < currentIndex
    );
  }, [currentIndex]);

  // Calculate live stats from visible candles
  const stats = useMemo(() => {
    if (visibleCandles.length === 0) return null;
    const first = visibleCandles[0];
    const last = visibleCandles[visibleCandles.length - 1];
    const change = last.close - first.open;
    const changePct = (change / first.open) * 100;
    const high = Math.max(...visibleCandles.map((c) => c.high));
    const low = Math.min(...visibleCandles.map((c) => c.low));
    const totalVolume = visibleCandles.reduce((sum, c) => sum + c.volume, 0);
    return {
      price: last.close,
      change,
      changePct,
      high,
      low,
      volume: totalVolume,
      time: last.time,
    };
  }, [visibleCandles]);

  // Trade stats for visible trades
  const tradeStats = useMemo(() => {
    if (visibleTrades.length === 0) return null;
    const wins = visibleTrades.filter((t: any) => t.pnl > 0).length;
    const losses = visibleTrades.filter((t: any) => t.pnl <= 0).length;
    const totalR = visibleTrades.reduce((sum: number, t: any) => sum + t.pnl_r, 0);
    const winRate = visibleTrades.length > 0 ? (wins / visibleTrades.length) * 100 : 0;
    return { wins, losses, totalR, winRate, total: visibleTrades.length };
  }, [visibleTrades]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-[#00e676] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-mono text-muted-foreground">
            Carregando dados BTC...
          </span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-center">
          <WifiOff className="w-8 h-8 text-[#ff3b3b]" />
          <span className="text-sm font-mono text-[#ff3b3b]">{error}</span>
          <button
            onClick={refetch}
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-mono bg-secondary rounded-sm border border-border/50 hover:bg-secondary/80"
          >
            <RefreshCw className="w-3 h-3" /> Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[1800px] mx-auto px-4 py-2 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-[#f7931a] animate-pulse" />
              <h1 className="text-sm font-bold tracking-tight font-sans">
                SMC MARKET REPLAY
              </h1>
            </div>
            <span className="text-[10px] font-mono text-muted-foreground px-2 py-0.5 bg-secondary rounded-sm">
              BTCUSDT
            </span>
            <span className="text-[10px] font-mono text-muted-foreground px-2 py-0.5 bg-secondary rounded-sm">
              5min
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 bg-[#00e676]/10 border border-[#00e676]/30 rounded-sm text-[#00e676]">
              <Wifi className="w-3 h-3 inline mr-1" />
              LIVE DATA
            </span>
          </div>
          <div className="flex items-center gap-4 text-[10px] font-mono text-muted-foreground">
            {stats && (
              <>
                <span className="flex items-center gap-1">
                  <Activity className="w-3 h-3" />
                  {stats.price.toFixed(2)} USDT
                </span>
                <span
                  className={`flex items-center gap-1 ${
                    stats.change >= 0 ? "text-[#00e676]" : "text-[#ff3b3b]"
                  }`}
                >
                  {stats.change >= 0 ? "+" : ""}
                  {stats.change.toFixed(2)} ({stats.changePct.toFixed(2)}%)
                </span>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-[1800px] mx-auto px-4 py-3 space-y-3">
        {/* Replay Controls */}
        <ReplayControls
          isPlaying={isPlaying}
          speed={speed}
          currentIndex={currentIndex}
          totalCandles={candles.length}
          onPlay={play}
          onPause={pause}
          onReset={reset}
          onSpeedChange={changeSpeed}
          onSeek={seek}
          onStepForward={stepForward}
        />

        {/* Chart */}
        <section className="bg-card border border-border/50 rounded-sm overflow-hidden">
          <div className="px-3 py-1.5 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-[#f7931a]" />
              <h2 className="text-[11px] font-semibold uppercase tracking-wider">
                BTC/USDT — Market Replay
              </h2>
              {tradeStats && (
                <span className="text-[10px] font-mono ml-3 px-2 py-0.5 bg-secondary/50 rounded-sm">
                  {tradeStats.total} trades | {tradeStats.wins}W {tradeStats.losses}L |{" "}
                  <span className={tradeStats.totalR >= 0 ? "text-[#00e676]" : "text-[#ff3b3b]"}>
                    {tradeStats.totalR >= 0 ? "+" : ""}{tradeStats.totalR.toFixed(1)}R
                  </span>
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-[10px] font-mono text-muted-foreground">
              {stats && <span>{stats.time}</span>}
              <button
                onClick={refetch}
                className="flex items-center gap-1 px-2 py-0.5 bg-secondary/50 rounded-sm border border-border/30 hover:bg-secondary transition-colors"
                title="Recarregar dados"
              >
                <RefreshCw className="w-3 h-3" /> Reload
              </button>
            </div>
          </div>
          <div className="h-[500px]">
            <CandlestickChart
              candles={visibleCandles}
              orderBlocks={visibleOrderBlocks}
              trades={visibleTrades}
              pendingOrders={visiblePendingOrders}
              swingHighs={visibleSwingHighs}
              swingLows={visibleSwingLows}
            />
          </div>
        </section>

        {/* Stats Cards */}
        <section className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
          {stats && (
            <>
              <div className="bg-card border border-border/50 rounded-sm p-3">
                <div className="text-[10px] font-mono text-muted-foreground uppercase">Preço</div>
                <div className="text-base font-bold font-mono text-foreground">
                  ${stats.price.toFixed(0)}
                </div>
              </div>
              <div className="bg-card border border-border/50 rounded-sm p-3">
                <div className="text-[10px] font-mono text-muted-foreground uppercase">Variação</div>
                <div className={`text-base font-bold font-mono ${stats.change >= 0 ? "text-[#00e676]" : "text-[#ff3b3b]"}`}>
                  {stats.changePct >= 0 ? "+" : ""}{stats.changePct.toFixed(2)}%
                </div>
              </div>
              <div className="bg-card border border-border/50 rounded-sm p-3">
                <div className="text-[10px] font-mono text-muted-foreground uppercase">High</div>
                <div className="text-base font-bold font-mono text-[#00e676]">
                  ${stats.high.toFixed(0)}
                </div>
              </div>
              <div className="bg-card border border-border/50 rounded-sm p-3">
                <div className="text-[10px] font-mono text-muted-foreground uppercase">Low</div>
                <div className="text-base font-bold font-mono text-[#ff3b3b]">
                  ${stats.low.toFixed(0)}
                </div>
              </div>
            </>
          )}
          {tradeStats ? (
            <>
              <div className="bg-card border border-[#00e676]/30 rounded-sm p-3">
                <div className="text-[10px] font-mono text-muted-foreground uppercase flex items-center gap-1">
                  <Target className="w-3 h-3" /> Win Rate
                </div>
                <div className="text-base font-bold font-mono text-[#00e676]">
                  {tradeStats.winRate.toFixed(0)}%
                </div>
              </div>
              <div className="bg-card border border-border/50 rounded-sm p-3">
                <div className="text-[10px] font-mono text-muted-foreground uppercase flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" /> Wins
                </div>
                <div className="text-base font-bold font-mono text-[#00e676]">
                  {tradeStats.wins}
                </div>
              </div>
              <div className="bg-card border border-border/50 rounded-sm p-3">
                <div className="text-[10px] font-mono text-muted-foreground uppercase flex items-center gap-1">
                  <TrendingDown className="w-3 h-3" /> Losses
                </div>
                <div className="text-base font-bold font-mono text-[#ff3b3b]">
                  {tradeStats.losses}
                </div>
              </div>
              <div className="bg-card border border-border/50 rounded-sm p-3">
                <div className="text-[10px] font-mono text-muted-foreground uppercase">P&L (R)</div>
                <div className={`text-base font-bold font-mono ${tradeStats.totalR >= 0 ? "text-[#00e676]" : "text-[#ff3b3b]"}`}>
                  {tradeStats.totalR >= 0 ? "+" : ""}{tradeStats.totalR.toFixed(1)}R
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="bg-card border border-border/50 rounded-sm p-3 col-span-4">
                <div className="text-[10px] font-mono text-muted-foreground text-center py-1">
                  Avance o replay para ver os trades aparecendo...
                </div>
              </div>
            </>
          )}
        </section>

        {/* Trade Log */}
        {visibleTrades.length > 0 && (
          <section className="bg-card border border-border/50 rounded-sm overflow-hidden">
            <div className="px-3 py-1.5 border-b border-border/30 flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-[#ffd700]" />
              <h2 className="text-[11px] font-semibold uppercase tracking-wider">
                Trade Log
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[10px] font-mono">
                <thead>
                  <tr className="border-b border-border/30 text-muted-foreground">
                    <th className="px-2 py-1 text-left">#</th>
                    <th className="px-2 py-1 text-left">Dir</th>
                    <th className="px-2 py-1 text-right">Entry</th>
                    <th className="px-2 py-1 text-right">Exit</th>
                    <th className="px-2 py-1 text-right">P&L</th>
                    <th className="px-2 py-1 text-right">R</th>
                    <th className="px-2 py-1 text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleTrades.map((t: any, i: number) => {
                    const isWin = t.pnl > 0;
                    return (
                      <tr key={t.id} className="border-b border-border/10 hover:bg-secondary/20">
                        <td className="px-2 py-1">{i + 1}</td>
                        <td className="px-2 py-1">
                          <span className={t.direction === "bullish" ? "text-[#00e676]" : "text-[#ff9100]"}>
                            {t.direction === "bullish" ? "LONG" : "SHORT"}
                          </span>
                        </td>
                        <td className="px-2 py-1 text-right">{t.entry_price.toFixed(2)}</td>
                        <td className="px-2 py-1 text-right">{t.exit_price.toFixed(2)}</td>
                        <td className={`px-2 py-1 text-right font-semibold ${isWin ? "text-[#00e676]" : "text-[#ff3b3b]"}`}>
                          {isWin ? "+" : ""}{t.pnl.toFixed(2)}
                        </td>
                        <td className={`px-2 py-1 text-right font-semibold ${isWin ? "text-[#00e676]" : "text-[#ff3b3b]"}`}>
                          {t.pnl_r > 0 ? "+" : ""}{t.pnl_r.toFixed(1)}R
                        </td>
                        <td className="px-2 py-1 text-center">
                          {isWin ? "✅ TP" : "❌ SL"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
