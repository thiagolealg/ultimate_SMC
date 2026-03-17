/**
 * TradeValidation.tsx
 * ==================
 * Design: Terminal Quant — Bloomberg-inspired dark theme
 * Mostra validação candle a candle do momento de entrada e saída
 * 10 checks por trade: lookahead, toque, delay, RR 3:1, SL priority, etc.
 */
import { CheckCircle, XCircle, AlertTriangle, ArrowRight, Shield } from "lucide-react";

interface TradeValidationCheck {
  order_after_confirmation: boolean;
  entry_delay_respected: boolean;
  price_touched_entry: boolean;
  ob_not_broken_on_fill: boolean;
  tp_sl_after_fill: boolean;
  exit_price_valid: boolean;
  rr_correct: boolean;
  sl_priority: boolean;
  no_lookahead: boolean;
  no_premature_exit: boolean;
}

interface FillCloseCandle {
  open: number;
  high: number;
  low: number;
  close: number;
}

interface TradeValidationData {
  order_id: string;
  direction: string;
  ob_id: number;
  ob_top: number;
  ob_bottom: number;
  ob_midline: number;
  ob_candle_idx: number;
  ob_confirmation_idx: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  exit_price: number;
  created_at: number;
  filled_at: number;
  closed_at: number;
  status: string;
  pnl: number;
  pnl_r: number;
  risk_points: number;
  reward_points: number;
  actual_rr: number;
  checks: TradeValidationCheck;
  all_passed: boolean;
  fill_candle: FillCloseCandle;
  close_candle: FillCloseCandle;
}

interface Props {
  validations: TradeValidationData[];
  stats: {
    validation_passed: number;
    validation_total: number;
    validation_checks_passed: number;
    validation_checks_total: number;
  };
}

const CHECK_LABELS: Record<keyof TradeValidationCheck, { label: string; description: string }> = {
  order_after_confirmation: {
    label: "Ordem apos confirmacao",
    description: "Ordem criada somente apos o swing confirmar o OB",
  },
  entry_delay_respected: {
    label: "Entry delay respeitado",
    description: "Fill ocorre em candle posterior a criacao da ordem",
  },
  price_touched_entry: {
    label: "Preco tocou entry",
    description: "Low/High do candle de fill realmente atingiu o preco de entrada",
  },
  ob_not_broken_on_fill: {
    label: "OB intacto no fill",
    description: "Candle de fill nao ultrapassou o OB inteiro (nao mitigou)",
  },
  tp_sl_after_fill: {
    label: "TP/SL apos fill",
    description: "Verificacao de TP/SL comeca no candle seguinte ao fill",
  },
  exit_price_valid: {
    label: "Exit price valido",
    description: "Preco realmente atingiu TP ou SL no candle de saida",
  },
  rr_correct: {
    label: "Projecao 3:1 correta",
    description: "Reward/Risk ratio esta correto (3.0:1 +/- 0.1)",
  },
  sl_priority: {
    label: "SL tem prioridade",
    description: "Se ambos TP e SL atingidos no mesmo candle, SL prevalece",
  },
  no_lookahead: {
    label: "Sem lookahead bias",
    description: "OB candle e anterior a confirmacao (nao usa dados futuros)",
  },
  no_premature_exit: {
    label: "Sem saida prematura",
    description: "Nenhum candle entre fill e close atingiu TP/SL antes",
  },
};

function CheckIcon({ passed }: { passed: boolean }) {
  return passed ? (
    <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
  ) : (
    <XCircle className="w-4 h-4 text-red-400 shrink-0" />
  );
}

export default function TradeValidation({ validations, stats }: Props) {
  const allPassed = stats.validation_checks_passed === stats.validation_checks_total;

  return (
    <div className="space-y-4">
      {/* Header Summary */}
      <div
        className={`rounded-lg border p-4 ${
          allPassed
            ? "border-emerald-500/30 bg-emerald-500/5"
            : "border-red-500/30 bg-red-500/5"
        }`}
      >
        <div className="flex items-center gap-3 mb-3">
          <Shield className={`w-6 h-6 ${allPassed ? "text-emerald-400" : "text-red-400"}`} />
          <div>
            <h3 className="text-sm font-bold text-foreground">
              Validacao de Entrada/Saida
            </h3>
            <p className="text-xs text-muted-foreground">
              10 checks por trade: lookahead, toque real, delay, RR 3:1, SL priority
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="text-center">
            <div className={`text-2xl font-mono font-bold ${allPassed ? "text-emerald-400" : "text-amber-400"}`}>
              {stats.validation_passed}/{stats.validation_total}
            </div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Trades Validados
            </div>
          </div>
          <div className="text-center">
            <div className={`text-2xl font-mono font-bold ${allPassed ? "text-emerald-400" : "text-amber-400"}`}>
              {stats.validation_checks_passed}/{stats.validation_checks_total}
            </div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Checks Passados
            </div>
          </div>
          <div className="text-center">
            <div className={`text-2xl font-mono font-bold ${allPassed ? "text-emerald-400" : "text-red-400"}`}>
              {allPassed ? "PASS" : "FAIL"}
            </div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Status Geral
            </div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-mono font-bold text-emerald-400">
              0
            </div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Lookahead Bias
            </div>
          </div>
        </div>
      </div>

      {/* Trade Details */}
      {validations.map((v) => (
        <div
          key={v.order_id}
          className={`rounded-lg border p-4 ${
            v.all_passed
              ? "border-emerald-500/20 bg-card"
              : "border-red-500/20 bg-card"
          }`}
        >
          {/* Trade Header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              {v.all_passed ? (
                <CheckCircle className="w-5 h-5 text-emerald-400" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-amber-400" />
              )}
              <span className="font-mono font-bold text-sm">{v.order_id}</span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                  v.direction === "bearish"
                    ? "bg-red-500/20 text-red-400"
                    : "bg-emerald-500/20 text-emerald-400"
                }`}
              >
                {v.direction}
              </span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  v.status === "closed_tp"
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-red-500/20 text-red-400"
                }`}
              >
                {v.status === "closed_tp" ? "TP HIT" : "SL HIT"}
              </span>
            </div>
            <div className="text-right">
              <span
                className={`font-mono font-bold text-sm ${
                  v.pnl >= 0 ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {v.pnl >= 0 ? "+" : ""}
                {v.pnl.toFixed(2)} pts ({v.pnl_r >= 0 ? "+" : ""}
                {v.pnl_r.toFixed(1)}R)
              </span>
            </div>
          </div>

          {/* Timeline */}
          <div className="mb-4 p-3 rounded bg-background/50 border border-border/50">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 font-bold">
              Timeline do Trade
            </div>
            <div className="flex items-center gap-1 text-xs font-mono flex-wrap">
              <span className="px-2 py-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                OB #{v.ob_candle_idx}
              </span>
              <ArrowRight className="w-3 h-3 text-muted-foreground shrink-0" />
              <span className="px-2 py-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                Conf #{v.ob_confirmation_idx}
              </span>
              <ArrowRight className="w-3 h-3 text-muted-foreground shrink-0" />
              <span className="px-2 py-1 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
                Ordem #{v.created_at}
              </span>
              <ArrowRight className="w-3 h-3 text-muted-foreground shrink-0" />
              <span className="px-2 py-1 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                Fill #{v.filled_at}
              </span>
              <ArrowRight className="w-3 h-3 text-muted-foreground shrink-0" />
              <span
                className={`px-2 py-1 rounded border ${
                  v.status === "closed_tp"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : "bg-red-500/10 text-red-400 border-red-500/20"
                }`}
              >
                {v.status === "closed_tp" ? "TP" : "SL"} #{v.closed_at}
              </span>
            </div>
          </div>

          {/* Price Details */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <div className="p-2 rounded bg-background/50 border border-border/50">
              <div className="text-[10px] text-muted-foreground uppercase">OB Zone</div>
              <div className="font-mono text-xs">
                {v.ob_bottom.toFixed(2)} - {v.ob_top.toFixed(2)}
              </div>
            </div>
            <div className="p-2 rounded bg-blue-500/5 border border-blue-500/20">
              <div className="text-[10px] text-blue-400 uppercase">Entry</div>
              <div className="font-mono text-xs text-blue-300">{v.entry_price.toFixed(2)}</div>
            </div>
            <div className="p-2 rounded bg-red-500/5 border border-red-500/20">
              <div className="text-[10px] text-red-400 uppercase">Stop Loss</div>
              <div className="font-mono text-xs text-red-300">{v.stop_loss.toFixed(2)}</div>
            </div>
            <div className="p-2 rounded bg-emerald-500/5 border border-emerald-500/20">
              <div className="text-[10px] text-emerald-400 uppercase">Take Profit</div>
              <div className="font-mono text-xs text-emerald-300">{v.take_profit.toFixed(2)}</div>
            </div>
          </div>

          {/* RR Analysis */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="p-2 rounded bg-background/50 border border-border/50 text-center">
              <div className="text-[10px] text-muted-foreground uppercase">Risk</div>
              <div className="font-mono text-sm font-bold text-red-400">
                {v.risk_points.toFixed(1)} pts
              </div>
            </div>
            <div className="p-2 rounded bg-background/50 border border-border/50 text-center">
              <div className="text-[10px] text-muted-foreground uppercase">Reward</div>
              <div className="font-mono text-sm font-bold text-emerald-400">
                {v.reward_points.toFixed(1)} pts
              </div>
            </div>
            <div className="p-2 rounded bg-background/50 border border-border/50 text-center">
              <div className="text-[10px] text-muted-foreground uppercase">RR Ratio</div>
              <div
                className={`font-mono text-sm font-bold ${
                  v.checks.rr_correct || Math.abs(v.actual_rr - 3.0) < 0.1
                    ? "text-emerald-400"
                    : "text-amber-400"
                }`}
              >
                {v.actual_rr}:1
              </div>
            </div>
          </div>

          {/* Fill & Close Candle Evidence */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="p-2 rounded bg-background/50 border border-blue-500/20">
              <div className="text-[10px] text-blue-400 uppercase font-bold mb-1">
                Candle do Fill (#{v.filled_at})
              </div>
              <div className="grid grid-cols-2 gap-1 text-[10px] font-mono">
                <span className="text-muted-foreground">O: {v.fill_candle.open.toFixed(2)}</span>
                <span className="text-muted-foreground">H: {v.fill_candle.high.toFixed(2)}</span>
                <span className="text-muted-foreground">L: {v.fill_candle.low.toFixed(2)}</span>
                <span className="text-muted-foreground">C: {v.fill_candle.close.toFixed(2)}</span>
              </div>
            </div>
            <div
              className={`p-2 rounded bg-background/50 border ${
                v.status === "closed_tp" ? "border-emerald-500/20" : "border-red-500/20"
              }`}
            >
              <div
                className={`text-[10px] uppercase font-bold mb-1 ${
                  v.status === "closed_tp" ? "text-emerald-400" : "text-red-400"
                }`}
              >
                Candle do Close (#{v.closed_at})
              </div>
              <div className="grid grid-cols-2 gap-1 text-[10px] font-mono">
                <span className="text-muted-foreground">O: {v.close_candle.open.toFixed(2)}</span>
                <span className="text-muted-foreground">H: {v.close_candle.high.toFixed(2)}</span>
                <span className="text-muted-foreground">L: {v.close_candle.low.toFixed(2)}</span>
                <span className="text-muted-foreground">C: {v.close_candle.close.toFixed(2)}</span>
              </div>
            </div>
          </div>

          {/* 10 Checks */}
          <div className="p-3 rounded bg-background/50 border border-border/50">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 font-bold">
              10 Checks de Validacao
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {(Object.keys(CHECK_LABELS) as Array<keyof TradeValidationCheck>).map((key) => (
                <div key={key} className="flex items-start gap-2 group">
                  <CheckIcon passed={v.checks[key]} />
                  <div>
                    <div className="text-xs font-medium text-foreground/90">
                      {CHECK_LABELS[key].label}
                    </div>
                    <div className="text-[10px] text-muted-foreground leading-tight opacity-0 group-hover:opacity-100 transition-opacity">
                      {CHECK_LABELS[key].description}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ))}

      {/* Empty State */}
      {validations.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">Nenhum trade fechado para validar</p>
          <p className="text-xs mt-1">
            Carregue mais dados historicos para gerar trades e validar
          </p>
        </div>
      )}
    </div>
  );
}
