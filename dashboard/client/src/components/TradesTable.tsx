/**
 * TradesTable — Tabela de trades fechados e pendentes
 * Design: Terminal Quant — monospace, P&L colorido
 */

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
  patterns?: string[];
  confidence?: number;
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

interface TradesTableProps {
  trades: Trade[];
  pendingOrders: PendingOrder[];
}

export function TradesTable({ trades, pendingOrders }: TradesTableProps) {
  return (
    <div className="space-y-3">
      {/* Closed Trades */}
      <div>
        <h4 className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1 px-2">
          Trades Fechados ({trades.length})
        </h4>
        <div className="overflow-auto max-h-[200px]">
          <table className="w-full text-[11px] font-mono">
            <thead className="sticky top-0 bg-card z-10">
              <tr className="text-muted-foreground text-left border-b border-border/50">
                <th className="px-2 py-1 font-medium">ID</th>
                <th className="px-2 py-1 font-medium">DIR</th>
                <th className="px-2 py-1 font-medium text-right">ENTRY</th>
                <th className="px-2 py-1 font-medium text-right">EXIT</th>
                <th className="px-2 py-1 font-medium text-right">SL</th>
                <th className="px-2 py-1 font-medium text-right">TP</th>
                <th className="px-2 py-1 font-medium text-right">P&L</th>
                <th className="px-2 py-1 font-medium text-right">P&L (R)</th>
                <th className="px-2 py-1 font-medium">STATUS</th>
                <th className="px-2 py-1 font-medium">PATTERNS</th>
                <th className="px-2 py-1 font-medium text-right">OB#</th>
              </tr>
            </thead>
            <tbody>
              {trades.length === 0 ? (
                <tr>
                  <td colSpan={11} className="px-2 py-4 text-center text-muted-foreground">
                    Nenhum trade fechado
                  </td>
                </tr>
              ) : (
                trades.map((t) => {
                  const isWin = t.pnl > 0;
                  const pnlColor = isWin ? "text-[#00e676]" : "text-[#ff3b3b]";
                  const dirColor = t.direction === "bullish" ? "text-[#00e676]" : "text-[#ff9100]";

                  return (
                    <tr key={t.id} className="border-b border-border/20 hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                      <td className="px-2 py-1 text-foreground">{t.id}</td>
                      <td className={`px-2 py-1 font-semibold ${dirColor}`}>
                        {t.direction === "bullish" ? "LONG" : "SHORT"}
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums">{t.entry_price.toFixed(1)}</td>
                      <td className="px-2 py-1 text-right tabular-nums">{t.exit_price.toFixed(1)}</td>
                      <td className="px-2 py-1 text-right tabular-nums text-[#ff3b3b]/60">{t.sl.toFixed(1)}</td>
                      <td className="px-2 py-1 text-right tabular-nums text-[#00e676]/60">{t.tp.toFixed(1)}</td>
                      <td className={`px-2 py-1 text-right tabular-nums font-semibold ${pnlColor}`}>
                        {t.pnl > 0 ? "+" : ""}{t.pnl.toFixed(1)}
                      </td>
                      <td className={`px-2 py-1 text-right tabular-nums font-semibold ${pnlColor}`}>
                        {t.pnl_r > 0 ? "+" : ""}{t.pnl_r.toFixed(1)}R
                      </td>
                      <td className="px-2 py-1">
                        <span className={`px-1.5 py-0.5 rounded-sm text-[10px] font-semibold ${isWin ? "bg-[#00e676]/10 text-[#00e676]" : "bg-[#ff3b3b]/10 text-[#ff3b3b]"}`}>
                          {t.status === "closed_tp" ? "TP" : "SL"}
                        </span>
                      </td>
                      <td className="px-2 py-1">
                        <div className="flex gap-0.5">
                          {(t.patterns || []).map((p, i) => (
                            <span key={i} className="px-1 py-0.5 rounded-sm text-[9px] bg-[rgba(255,255,255,0.05)] text-muted-foreground">
                              {p}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums text-muted-foreground">#{t.ob_id}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pending Orders */}
      <div>
        <h4 className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1 px-2">
          Ordens Pendentes ({pendingOrders.length})
        </h4>
        <div className="overflow-auto max-h-[150px]">
          <table className="w-full text-[11px] font-mono">
            <thead className="sticky top-0 bg-card z-10">
              <tr className="text-muted-foreground text-left border-b border-border/50">
                <th className="px-2 py-1 font-medium">ID</th>
                <th className="px-2 py-1 font-medium">DIR</th>
                <th className="px-2 py-1 font-medium text-right">ENTRY</th>
                <th className="px-2 py-1 font-medium text-right">SL</th>
                <th className="px-2 py-1 font-medium text-right">TP</th>
                <th className="px-2 py-1 font-medium text-right">RR</th>
                <th className="px-2 py-1 font-medium text-right">OB#</th>
                <th className="px-2 py-1 font-medium text-right">CRIADO</th>
              </tr>
            </thead>
            <tbody>
              {pendingOrders.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-2 py-4 text-center text-muted-foreground">
                    Nenhuma ordem pendente
                  </td>
                </tr>
              ) : (
                pendingOrders.map((po) => {
                  const dirColor = po.direction === "bullish" ? "text-[#00e676]" : "text-[#ff9100]";
                  const risk = Math.abs(po.entry_price - po.sl);
                  const reward = Math.abs(po.tp - po.entry_price);
                  const rr = risk > 0 ? (reward / risk).toFixed(1) : "—";

                  return (
                    <tr key={po.id} className="border-b border-border/20 hover:bg-[rgba(255,235,59,0.02)] transition-colors">
                      <td className="px-2 py-1 text-[#ffd700]">{po.id}</td>
                      <td className={`px-2 py-1 font-semibold ${dirColor}`}>
                        {po.direction === "bullish" ? "LONG" : "SHORT"}
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums">{po.entry_price.toFixed(1)}</td>
                      <td className="px-2 py-1 text-right tabular-nums text-[#ff3b3b]/60">{po.sl.toFixed(1)}</td>
                      <td className="px-2 py-1 text-right tabular-nums text-[#00e676]/60">{po.tp.toFixed(1)}</td>
                      <td className="px-2 py-1 text-right tabular-nums text-muted-foreground">{rr}:1</td>
                      <td className="px-2 py-1 text-right tabular-nums text-muted-foreground">#{po.ob_id}</td>
                      <td className="px-2 py-1 text-right tabular-nums text-muted-foreground">C{po.created_at}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
