import { Header } from "@/components/layout/header"
import { StatsCards } from "@/components/dashboard/stats-cards"
import { RecentMatches } from "@/components/dashboard/recent-matches"
import { CourtDistribution } from "@/components/dashboard/court-distribution"
import { MatchTrendChart } from "@/components/dashboard/match-trend-chart"
import { TopWatches } from "@/components/dashboard/top-watches"

export const dynamic = "force-dynamic"

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <Header title="Dashboard" description="Judgment monitoring overview" />
      <StatsCards />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 h-full">
          <RecentMatches />
        </div>
        <div className="h-full">
          <CourtDistribution />
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <MatchTrendChart />
        </div>
        <div className="h-full">
          <TopWatches />
        </div>
      </div>
    </div>
  )
}
