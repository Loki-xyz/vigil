"use client"

import { useQuery } from "@tanstack/react-query"
import { supabase } from "@/lib/supabase/client"

interface CourtCount {
  court: string
  count: number
}

export function useCourtDistribution(days = 30) {
  return useQuery({
    queryKey: ["dashboard", "court-distribution", days],
    queryFn: async () => {
      const since = new Date()
      since.setDate(since.getDate() - days)
      const { data, error } = await supabase
        .from("watch_matches")
        .select("judgments(court)")
        .gte("matched_at", since.toISOString())
      if (error) throw error

      const counts = new Map<string, number>()
      for (const row of data ?? []) {
        const court =
          (row.judgments as unknown as { court: string } | null)?.court ??
          "Unknown"
        counts.set(court, (counts.get(court) ?? 0) + 1)
      }
      return Array.from(counts, ([court, count]) => ({
        court,
        count,
      })).sort((a, b) => b.count - a.count) as CourtCount[]
    },
  })
}
