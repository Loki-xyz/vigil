"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { AreaChart } from "@tremor/react"
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
          <AreaChart
            data={chartData}
            index="date"
            categories={["matches"]}
            colors={["indigo"]}
            showAnimation
            className="h-72"
            curveType="monotone"
            showGridLines={false}
          />
        )}
      </CardContent>
    </Card>
  )
}
