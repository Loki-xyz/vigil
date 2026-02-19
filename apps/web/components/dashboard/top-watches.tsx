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
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts"
import { useTopWatches } from "@/lib/hooks/use-top-watches"

export function TopWatches() {
  const { data, isLoading } = useTopWatches()

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Top Watches (30 Days)</CardTitle>
        <CardAction>
          <Link
            href="/watches"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Manage
          </Link>
        </CardAction>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-6 flex-1 rounded" />
                <Skeleton className="h-4 w-8" />
              </div>
            ))}
          </div>
        ) : !data?.length ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No matches yet.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={data.length * 40 + 20}>
            <BarChart data={data} layout="vertical" margin={{ left: 0, right: 20 }}>
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="name"
                width={120}
                tick={{ fontSize: 12, fill: "var(--color-muted-foreground, #888)" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--color-popover, #fff)",
                  border: "1px solid var(--color-border, #e5e7eb)",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
              />
              <Bar
                dataKey="value"
                fill="var(--color-indigo-500, #6366f1)"
                radius={[0, 4, 4, 0]}
                animationDuration={1000}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
