"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Eye, Sparkles, TrendingUp, Bell } from "lucide-react"
import {
  useActiveWatchCount,
  useMatchesToday,
  useMatchesThisWeek,
  useAlertsDeliveredCount,
} from "@/lib/hooks/use-dashboard"

export function StatsCards() {
  const activeWatches = useActiveWatchCount()
  const matchesToday = useMatchesToday()
  const matchesWeek = useMatchesThisWeek()
  const alertsDelivered = useAlertsDeliveredCount()

  const cards = [
    {
      title: "Active Watches",
      value: activeWatches.data,
      icon: Eye,
      loading: activeWatches.isLoading,
    },
    {
      title: "New Today",
      value: matchesToday.data,
      icon: Sparkles,
      loading: matchesToday.isLoading,
    },
    {
      title: "This Week",
      value: matchesWeek.data,
      icon: TrendingUp,
      loading: matchesWeek.isLoading,
    },
    {
      title: "Alerts Delivered",
      value: alertsDelivered.data,
      icon: Bell,
      loading: alertsDelivered.isLoading,
    },
  ]

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.title}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {card.title}
            </CardTitle>
            <card.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {card.loading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <div className="text-2xl font-bold">{card.value ?? 0}</div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
