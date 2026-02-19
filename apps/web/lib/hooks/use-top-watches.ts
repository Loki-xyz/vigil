"use client"

import { useQuery } from "@tanstack/react-query"
import { supabase } from "@/lib/supabase/client"

interface WatchRank {
  name: string
  value: number
}

export function useTopWatches(days = 30, limit = 5) {
  return useQuery({
    queryKey: ["dashboard", "top-watches", days, limit],
    queryFn: async () => {
      const since = new Date()
      since.setDate(since.getDate() - days)
      const { data, error } = await supabase
        .from("watch_matches")
        .select("watches(name)")
        .gte("matched_at", since.toISOString())
      if (error) throw error

      const counts = new Map<string, number>()
      for (const row of data ?? []) {
        const name =
          (row.watches as unknown as { name: string } | null)?.name ??
          "Unknown"
        counts.set(name, (counts.get(name) ?? 0) + 1)
      }
      return Array.from(counts, ([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value)
        .slice(0, limit) as WatchRank[]
    },
  })
}
