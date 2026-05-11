/**
 * ReplayControls — Controles de replay de mercado
 * Play, Pause, Reset, Velocidade (1x, 2x, 5x, 10x), Barra de progresso
 */
import { Play, Pause, RotateCcw, SkipForward } from "lucide-react";

interface ReplayControlsProps {
  isPlaying: boolean;
  speed: number;
  currentIndex: number;
  totalCandles: number;
  onPlay: () => void;
  onPause: () => void;
  onReset: () => void;
  onSpeedChange: (speed: number) => void;
  onSeek: (index: number) => void;
  onStepForward: () => void;
}

const SPEEDS = [1, 2, 5, 10, 25];

export function ReplayControls({
  isPlaying,
  speed,
  currentIndex,
  totalCandles,
  onPlay,
  onPause,
  onReset,
  onSpeedChange,
  onSeek,
  onStepForward,
}: ReplayControlsProps) {
  const progress = totalCandles > 0 ? (currentIndex / totalCandles) * 100 : 0;

  return (
    <div className="flex flex-col gap-2 bg-card border border-border/50 rounded-sm p-3">
      {/* Progress bar */}
      <div className="flex items-center gap-3">
        <span className="text-[10px] font-mono text-muted-foreground w-16">
          {currentIndex}/{totalCandles}
        </span>
        <div className="flex-1 relative h-2 bg-secondary rounded-full overflow-hidden cursor-pointer"
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const pct = x / rect.width;
            const idx = Math.round(pct * totalCandles);
            onSeek(Math.max(1, Math.min(idx, totalCandles)));
          }}
        >
          <div
            className="absolute inset-y-0 left-0 bg-[#00e676] rounded-full transition-all duration-100"
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="text-[10px] font-mono text-muted-foreground w-12 text-right">
          {progress.toFixed(0)}%
        </span>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Play/Pause */}
          <button
            onClick={isPlaying ? onPause : onPlay}
            className="flex items-center justify-center w-8 h-8 rounded-sm bg-[#00e676]/10 border border-[#00e676]/30 hover:bg-[#00e676]/20 transition-colors"
            title={isPlaying ? "Pausar" : "Play"}
          >
            {isPlaying ? (
              <Pause className="w-4 h-4 text-[#00e676]" />
            ) : (
              <Play className="w-4 h-4 text-[#00e676]" />
            )}
          </button>

          {/* Step Forward */}
          <button
            onClick={onStepForward}
            disabled={isPlaying}
            className="flex items-center justify-center w-8 h-8 rounded-sm bg-secondary/50 border border-border/30 hover:bg-secondary transition-colors disabled:opacity-30"
            title="Avançar 1 candle"
          >
            <SkipForward className="w-4 h-4 text-muted-foreground" />
          </button>

          {/* Reset */}
          <button
            onClick={onReset}
            className="flex items-center justify-center w-8 h-8 rounded-sm bg-secondary/50 border border-border/30 hover:bg-secondary transition-colors"
            title="Reiniciar"
          >
            <RotateCcw className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>

        {/* Speed selector */}
        <div className="flex items-center gap-1">
          <span className="text-[10px] font-mono text-muted-foreground mr-2">SPEED:</span>
          {SPEEDS.map((s) => (
            <button
              key={s}
              onClick={() => onSpeedChange(s)}
              className={`px-2 py-1 text-[10px] font-mono rounded-sm border transition-colors ${
                speed === s
                  ? "bg-[#00e676]/20 border-[#00e676]/50 text-[#00e676]"
                  : "bg-secondary/30 border-border/30 text-muted-foreground hover:bg-secondary/50"
              }`}
            >
              {s}x
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
