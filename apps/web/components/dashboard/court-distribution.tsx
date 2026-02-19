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
import { DonutChart } from "@tremor/react"
import { useCourtDistribution } from "@/lib/hooks/use-court-distribution"

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
          <DonutChart
            data={data}
            index="court"
            category="count"
            colors={["purple", "blue", "red", "green", "yellow", "orange", "slate"]}
            showAnimation
            className="h-52"
            variant="pie"
          />
        )}
      </CardContent>
    </Card>
  )
}
