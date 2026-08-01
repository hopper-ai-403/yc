/** Dark-mode friendly Recharts palette (no gradients). */

export const CHART_COLORS = {
  primary: "hsl(var(--foreground))",
  muted: "hsl(var(--muted-foreground))",
  border: "hsl(var(--border))",
  success: "hsl(var(--success))",
  warning: "hsl(var(--warning))",
  destructive: "hsl(var(--destructive))",
  info: "hsl(var(--info))",
  series: [
    "hsl(var(--info))",
    "hsl(var(--success))",
    "hsl(var(--warning))",
    "hsl(217 70% 55%)",
    "hsl(280 45% 55%)",
    "hsl(340 55% 55%)",
    "hsl(160 40% 40%)",
    "hsl(30 70% 50%)",
    "hsl(200 50% 45%)",
  ],
} as const;

export const chartTooltipStyle = {
  backgroundColor: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "8px",
  fontSize: "12px",
  color: "hsl(var(--foreground))",
} as const;

export const chartAxisTick = {
  fill: "hsl(var(--muted-foreground))",
  fontSize: 11,
} as const;
