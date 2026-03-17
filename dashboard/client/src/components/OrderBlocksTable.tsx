/**
 * OrderBlocksTable — Tabela de OBs detectados
 * Design: Terminal Quant — monospace, cores por status
 */

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

interface OrderBlocksTableProps {
  orderBlocks: OrderBlock[];
}

export function OrderBlocksTable({ orderBlocks }: OrderBlocksTableProps) {
  return (
    <div className="overflow-auto max-h-[300px]">
      <table className="w-full text-[11px] font-mono">
        <thead className="sticky top-0 bg-card z-10">
          <tr className="text-muted-foreground text-left border-b border-border/50">
            <th className="px-2 py-1.5 font-medium">ID</th>
            <th className="px-2 py-1.5 font-medium">DIR</th>
            <th className="px-2 py-1.5 font-medium text-right">TOP</th>
            <th className="px-2 py-1.5 font-medium text-right">BOTTOM</th>
            <th className="px-2 py-1.5 font-medium text-right">SIZE</th>
            <th className="px-2 py-1.5 font-medium text-right">VOL.R</th>
            <th className="px-2 py-1.5 font-medium text-right">ATR.R</th>
            <th className="px-2 py-1.5 font-medium">STATUS</th>
            <th className="px-2 py-1.5 font-medium text-right">CANDLE</th>
            <th className="px-2 py-1.5 font-medium text-right">CONF</th>
            <th className="px-2 py-1.5 font-medium text-right">MIT</th>
          </tr>
        </thead>
        <tbody>
          {orderBlocks.map((ob) => {
            const isBullish = ob.direction === "bullish";
            const isActive = !ob.mitigated;
            const dirColor = isBullish ? "text-[#00e676]" : "text-[#ff9100]";
            const statusColor = isActive ? "text-[#00e676]" : "text-[#ff5252]";
            const rowBg = isActive ? "hover:bg-[rgba(0,230,118,0.03)]" : "hover:bg-[rgba(255,82,82,0.03)]";

            return (
              <tr key={ob.id} className={`border-b border-border/20 ${rowBg} transition-colors`}>
                <td className="px-2 py-1 text-foreground">#{ob.id}</td>
                <td className={`px-2 py-1 font-semibold ${dirColor}`}>
                  {isBullish ? "BULL" : "BEAR"}
                </td>
                <td className="px-2 py-1 text-right tabular-nums text-foreground">{ob.top.toFixed(1)}</td>
                <td className="px-2 py-1 text-right tabular-nums text-foreground">{ob.bottom.toFixed(1)}</td>
                <td className="px-2 py-1 text-right tabular-nums text-muted-foreground">{ob.ob_size.toFixed(1)}</td>
                <td className="px-2 py-1 text-right tabular-nums text-muted-foreground">{ob.volume_ratio.toFixed(2)}</td>
                <td className="px-2 py-1 text-right tabular-nums text-muted-foreground">{ob.ob_size_atr.toFixed(2)}</td>
                <td className={`px-2 py-1 font-semibold ${statusColor}`}>
                  {isActive ? "ATIVO" : "MITIGADO"}
                </td>
                <td className="px-2 py-1 text-right tabular-nums text-muted-foreground">{ob.ob_candle_index}</td>
                <td className="px-2 py-1 text-right tabular-nums text-muted-foreground">{ob.confirmation_index}</td>
                <td className="px-2 py-1 text-right tabular-nums text-muted-foreground">
                  {ob.mitigated_index ?? "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
