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
import { BarList } from "@tremor/react"
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
          <BarList data={data} color="indigo" showAnimation />
        )}
      </CardContent>
    </Card>
  )
}
