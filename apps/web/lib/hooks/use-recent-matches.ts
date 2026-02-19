"use client"

import { useQuery } from "@tanstack/react-query"
import { supabase } from "@/lib/supabase/client"
import type { WatchMatch } from "@/lib/supabase/types"

export function useRecentMatches(limit = 10) {
  return useQuery({
    queryKey: ["dashboard", "recent-matches", limit],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("watch_matches")
        .select("*, judgments(*), watches(name)")
        .order("matched_at", { ascending: false })
        .limit(limit)
      if (error) throw error
      return data as WatchMatch[]
    },
  })
}
