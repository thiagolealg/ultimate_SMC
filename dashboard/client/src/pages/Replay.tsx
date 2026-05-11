/**
 * Replay — Market Replay com dados BTC online
 * Permite assistir o mercado como se fosse em tempo real com controle de velocidade
 */
import { useMemo } from "react";
import { CandlestickChart } from "@/components/CandlestickChart";
import { ReplayControls } from "@/components/ReplayControls";
import { useBTCData } from "@/hooks/useBTCData";
import { useReplay } from "@/hooks/useReplay";
import { Activity, Wifi, WifiOff, RefreshCw } from "lucide-react";

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
                <span>H: {stats.high.toFixed(2)}</span>
                <span>L: {stats.low.toFixed(2)}</span>
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
              orderBlocks={[]}
              trades={[]}
              pendingOrders={[]}
              swingHighs={[]}
              swingLows={[]}
            />
          </div>
        </section>

        {/* Stats Cards */}
        {stats && (
          <section className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2">
            <div className="bg-card border border-border/50 rounded-sm p-3">
              <div className="text-[10px] font-mono text-muted-foreground uppercase">Preço Atual</div>
              <div className="text-lg font-bold font-mono text-foreground">
                ${stats.price.toFixed(2)}
              </div>
            </div>
            <div className="bg-card border border-border/50 rounded-sm p-3">
              <div className="text-[10px] font-mono text-muted-foreground uppercase">Variação</div>
              <div className={`text-lg font-bold font-mono ${stats.change >= 0 ? "text-[#00e676]" : "text-[#ff3b3b]"}`}>
                {stats.changePct >= 0 ? "+" : ""}{stats.changePct.toFixed(2)}%
              </div>
            </div>
            <div className="bg-card border border-border/50 rounded-sm p-3">
              <div className="text-[10px] font-mono text-muted-foreground uppercase">High</div>
              <div className="text-lg font-bold font-mono text-[#00e676]">
                ${stats.high.toFixed(2)}
              </div>
            </div>
            <div className="bg-card border border-border/50 rounded-sm p-3">
              <div className="text-[10px] font-mono text-muted-foreground uppercase">Low</div>
              <div className="text-lg font-bold font-mono text-[#ff3b3b]">
                ${stats.low.toFixed(2)}
              </div>
            </div>
            <div className="bg-card border border-border/50 rounded-sm p-3">
              <div className="text-[10px] font-mono text-muted-foreground uppercase">Volume</div>
              <div className="text-lg font-bold font-mono text-foreground">
                {stats.volume.toFixed(2)}
              </div>
            </div>
            <div className="bg-card border border-border/50 rounded-sm p-3">
              <div className="text-[10px] font-mono text-muted-foreground uppercase">Candles</div>
              <div className="text-lg font-bold font-mono text-foreground">
                {currentIndex}/{candles.length}
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
