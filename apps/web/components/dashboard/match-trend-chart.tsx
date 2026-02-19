"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { useMatchTrend } from "@/lib/hooks/use-match-trend"

export function MatchTrendChart() {
  const { data: chartData, isLoading } = useMatchTrend()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Match Trend (Last 30 Days)</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-72 w-full" />
        ) : !chartData?.length ? (
          <div className="flex h-72 items-center justify-center text-sm text-muted-foreground">
            No matches recorded yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={288}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="matchesGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--color-indigo-500, #6366f1)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--color-indigo-500, #6366f1)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12, fill: "var(--color-muted-foreground, #888)" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 12, fill: "var(--color-muted-foreground, #888)" }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--color-popover)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "8px",
                  fontSize: "12px",
                  color: "var(--color-popover-foreground)",
                }}
                itemStyle={{ color: "var(--color-popover-foreground)" }}
                labelStyle={{ color: "var(--color-popover-foreground)" }}
                formatter={(value: number | undefined) => [`${value ?? 0} matches`, null]}
              />
              <Area
                type="monotone"
                dataKey="matches"
                stroke="var(--color-indigo-500, #6366f1)"
                fill="url(#matchesGradient)"
                strokeWidth={2}
                animationDuration={1000}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
