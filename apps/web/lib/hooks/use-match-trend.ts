"use client"

import { useQuery } from "@tanstack/react-query"
import { supabase } from "@/lib/supabase/client"
import { format } from "date-fns"

interface MatchTrendPoint {
  date: string
  matches: number
}

function groupByDate(rows: { matched_at: string }[]): MatchTrendPoint[] {
  const counts = new Map<string, number>()
  for (const row of rows) {
    const day = format(new Date(row.matched_at), "MMM d")
    counts.set(day, (counts.get(day) ?? 0) + 1)
  }
  return Array.from(counts, ([date, matches]) => ({ date, matches }))
}

export function useMatchTrend(days = 30) {
  return useQuery({
    queryKey: ["dashboard", "match-trend", days],
    queryFn: async () => {
      const since = new Date()
      since.setDate(since.getDate() - days)
      const { data, error } = await supabase
        .from("watch_matches")
        .select("matched_at")
        .gte("matched_at", since.toISOString())
        .order("matched_at", { ascending: true })
      if (error) throw error
      return groupByDate(data ?? [])
    },
  })
}
