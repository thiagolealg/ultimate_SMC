/**
 * EngineConfig — Painel de configuração da engine
 * Design: Terminal Quant — display de parâmetros
 */

interface EngineConfigProps {
  config: {
    symbol: string;
    swing_length: number;
    risk_reward_ratio: number;
    min_volume_ratio: number;
    min_ob_size_atr: number;
    use_not_mitigated_filter: boolean;
    max_pending_candles: number;
    entry_delay_candles: number;
  };
}

export function EngineConfig({ config }: EngineConfigProps) {
  const params = [
    { label: "SYMBOL", value: config.symbol },
    { label: "SWING LENGTH", value: config.swing_length },
    { label: "RISK:REWARD", value: `1:${config.risk_reward_ratio}` },
    { label: "MIN VOL RATIO", value: config.min_volume_ratio.toFixed(1) },
    { label: "MIN OB SIZE (ATR)", value: config.min_ob_size_atr.toFixed(1) },
    { label: "UNMITIGATED FILTER", value: config.use_not_mitigated_filter ? "ON" : "OFF" },
    { label: "MAX PENDING", value: `${config.max_pending_candles} candles` },
    { label: "ENTRY DELAY", value: `${config.entry_delay_candles} candle(s)` },
  ];

  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px] font-mono">
      {params.map((p) => (
        <div key={p.label} className="flex justify-between items-center py-0.5 border-b border-border/20">
          <span className="text-muted-foreground uppercase tracking-wider text-[9px]">{p.label}</span>
          <span className="text-foreground font-medium tabular-nums">{p.value}</span>
        </div>
      ))}
    </div>
  );
}
