"use client"

import Link from "next/link"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardAction,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  type PieLabelRenderProps,
} from "recharts"
import { useCourtDistribution } from "@/lib/hooks/use-court-distribution"

const COLORS = ["#a855f7", "#3b82f6", "#ef4444", "#22c55e", "#eab308", "#f97316", "#64748b"]

const RADIAN = Math.PI / 180

function renderLabel({
  cx,
  cy,
  midAngle,
  innerRadius,
  outerRadius,
  percent,
}: PieLabelRenderProps) {
  const pct = (percent as number) * 100
  if (pct < 5) return null

  const radius =
    (innerRadius as number) +
    ((outerRadius as number) - (innerRadius as number)) * 0.5
  const x = (cx as number) + radius * Math.cos(-(midAngle as number) * RADIAN)
  const y = (cy as number) + radius * Math.sin(-(midAngle as number) * RADIAN)

  return (
    <text
      x={x}
      y={y}
      fill="#fff"
      textAnchor="middle"
      dominantBaseline="central"
      fontSize={11}
      fontWeight={500}
    >
      {`${pct.toFixed(0)}%`}
    </text>
  )
}

export function CourtDistribution() {
  const { data, isLoading } = useCourtDistribution()

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Courts (30 Days)</CardTitle>
        <CardAction>
          <Link
            href="/judgments"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            View All
          </Link>
        </CardAction>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-52 w-full" />
        ) : !data?.length ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No matches yet.
          </p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={data}
                  dataKey="count"
                  nameKey="court"
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={75}
                  paddingAngle={2}
                  animationDuration={1000}
                  label={renderLabel}
                  labelLine={false}
                  stroke="none"
                >
                  {data.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--color-popover)",
                    border: "1px solid var(--color-border)",
                    borderRadius: "8px",
                    fontSize: "12px",
                    color: "var(--color-popover-foreground)",
                  }}
                  itemStyle={{ color: "var(--color-popover-foreground)" }}
                  formatter={(value: number | undefined) => [`${value ?? 0} matches`, null]}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
              {data.map((entry, index) => (
                <div
                  key={entry.court}
                  className="flex items-center gap-1.5 min-w-0"
                >
                  <span
                    className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{
                      backgroundColor: COLORS[index % COLORS.length],
                    }}
                  />
                  <span
                    className="truncate text-xs text-muted-foreground"
                    title={entry.court}
                  >
                    {entry.court}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
