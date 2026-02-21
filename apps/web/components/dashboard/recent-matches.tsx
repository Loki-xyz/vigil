"use client"

import Link from "next/link"
import { ExternalLink } from "lucide-react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardAction,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { CourtBadge } from "@/components/judgments/court-badge"
import { formatRelativeTime } from "@/lib/utils"
import { useRecentMatches } from "@/lib/hooks/use-recent-matches"

export function RecentMatches() {
  const { data: matches, isLoading } = useRecentMatches()

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Recent Matches</CardTitle>
        <CardAction>
          <Link
            href="/judgments"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            See All
          </Link>
        </CardAction>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-4 flex-1" />
                <Skeleton className="h-5 w-24" />
                <Skeleton className="h-4 w-16" />
              </div>
            ))}
          </div>
        ) : !matches?.length ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No matches yet. Create a watch to start monitoring.
          </p>
        ) : (
          <div className="space-y-3">
            {matches.map((match) => (
              <div key={match.id} className="flex items-center gap-3 text-sm">
                <div className="min-w-0 flex-1">
                  <a
                    href={match.judgments?.ik_url || match.judgments?.external_url || undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium hover:underline truncate block"
                  >
                    {match.judgments?.title ?? "Unknown judgment"}
                    <ExternalLink className="inline ml-1 h-3 w-3 text-muted-foreground" />
                  </a>
                  <span className="text-xs text-muted-foreground">
                    via{" "}
                    {(match.watches as { name: string } | undefined)?.name ??
                      "Unknown watch"}
                  </span>
                </div>
                <CourtBadge court={match.judgments?.court ?? null} />
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  {formatRelativeTime(match.matched_at)}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
