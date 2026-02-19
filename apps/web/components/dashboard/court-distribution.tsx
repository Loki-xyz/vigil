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
          <ResponsiveContainer width="100%" height={208}>
            <PieChart>
              <Pie
                data={data}
                dataKey="count"
                nameKey="court"
                cx="50%"
                cy="50%"
                outerRadius={80}
                animationDuration={1000}
                label={(props: PieLabelRenderProps) => {
                  const { name, percent } = props
                  return `${name ?? ""} (${((percent as number) * 100).toFixed(0)}%)`
                }}
                labelLine={false}
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
                  backgroundColor: "var(--color-popover, #fff)",
                  border: "1px solid var(--color-border, #e5e7eb)",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
