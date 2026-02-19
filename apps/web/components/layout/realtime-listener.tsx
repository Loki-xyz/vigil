"use client"

import { useCallback } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { useRealtimeMatches, useRealtimeWatches } from "@/lib/hooks/use-realtime"
import type { WatchMatch } from "@/lib/supabase/types"

/**
 * Global real-time event listener.
 * Mounted once in the root layout to handle live updates
 * regardless of which page the user is on.
 */
export function RealtimeListener() {
  const queryClient = useQueryClient()

  const handleNewMatch = useCallback(
    (match: WatchMatch) => {
      toast.info("New judgment matched", {
        description: match.snippet ?? "A new match was found by the polling worker.",
      })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
      queryClient.invalidateQueries({ queryKey: ["watches"] })
      queryClient.invalidateQueries({ queryKey: ["judgments"] })
    },
    [queryClient]
  )

  const handleWatchUpdate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["watches"] })
    queryClient.invalidateQueries({ queryKey: ["dashboard"] })
  }, [queryClient])

  useRealtimeMatches(handleNewMatch)
  useRealtimeWatches(handleWatchUpdate)

  return null
}
