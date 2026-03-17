/**
 * KPI Card — Terminal Quant Style
 * Design: Dense data card with monospace numbers, subtle border glow
 */
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  trend?: "up" | "down" | "neutral";
  icon?: React.ReactNode;
  className?: string;
}

export function KpiCard({ label, value, subtitle, trend = "neutral", icon, className }: KpiCardProps) {
  const trendColor = trend === "up" ? "text-[oklch(0.75_0.18_155)]" : trend === "down" ? "text-[oklch(0.65_0.22_25)]" : "text-muted-foreground";
  const borderGlow = trend === "up" ? "border-[oklch(0.75_0.18_155/0.3)]" : trend === "down" ? "border-[oklch(0.65_0.22_25/0.3)]" : "border-border";

  return (
    <div className={cn(
      "bg-card border rounded-sm p-3 flex flex-col gap-1 transition-all duration-200 hover:border-[oklch(0.75_0.18_155/0.5)]",
      borderGlow,
      className
    )}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{label}</span>
        {icon && <span className="text-muted-foreground opacity-60">{icon}</span>}
      </div>
      <span className={cn("font-mono text-xl font-bold tabular-nums leading-none", trendColor)}>
        {value}
      </span>
      {subtitle && (
        <span className="text-[10px] font-mono text-muted-foreground">{subtitle}</span>
      )}
    </div>
  );
}
