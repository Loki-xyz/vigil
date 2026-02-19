"use client"

import { useEffect } from "react"
import { supabase } from "@/lib/supabase/client"
import type { WatchMatch } from "@/lib/supabase/types"

/**
 * Subscribe to new watch matches in real-time.
 * When the Python worker inserts a new match, the dashboard
 * updates instantly — no page refresh needed.
 */
export function useRealtimeMatches(onNewMatch: (match: WatchMatch) => void) {
  useEffect(() => {
    const channel = supabase
      .channel("watch_matches_changes")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "watch_matches" },
        (payload) => {
          onNewMatch(payload.new as WatchMatch)
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [onNewMatch])
}

export function useRealtimeWatches(onUpdate: () => void) {
  useEffect(() => {
    const channel = supabase
      .channel("watches_changes")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "watches" },
        () => {
          onUpdate()
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [onUpdate])
}
