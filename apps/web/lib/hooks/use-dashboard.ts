"use client"

import { useQuery } from "@tanstack/react-query"
import { supabase } from "@/lib/supabase/client"

export function useActiveWatchCount() {
  return useQuery({
    queryKey: ["dashboard", "active-watches"],
    queryFn: async () => {
      const { count, error } = await supabase
        .from("watches")
        .select("*", { count: "exact", head: true })
        .eq("is_active", true)
      if (error) throw error
      return count ?? 0
    },
  })
}

export function useMatchesToday() {
  return useQuery({
    queryKey: ["dashboard", "matches-today"],
    queryFn: async () => {
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const { count, error } = await supabase
        .from("watch_matches")
        .select("*", { count: "exact", head: true })
        .gte("matched_at", today.toISOString())
      if (error) throw error
      return count ?? 0
    },
  })
}

export function useMatchesThisWeek() {
  return useQuery({
    queryKey: ["dashboard", "matches-week"],
    queryFn: async () => {
      const weekAgo = new Date()
      weekAgo.setDate(weekAgo.getDate() - 7)
      weekAgo.setHours(0, 0, 0, 0)
      const { count, error } = await supabase
        .from("watch_matches")
        .select("*", { count: "exact", head: true })
        .gte("matched_at", weekAgo.toISOString())
      if (error) throw error
      return count ?? 0
    },
  })
}

export function useAlertsDeliveredCount() {
  return useQuery({
    queryKey: ["dashboard", "alerts-delivered-7d"],
    queryFn: async () => {
      const weekAgo = new Date()
      weekAgo.setDate(weekAgo.getDate() - 7)
      weekAgo.setHours(0, 0, 0, 0)
      const { count, error } = await supabase
        .from("notification_log")
        .select("*", { count: "exact", head: true })
        .eq("status", "sent")
        .gte("created_at", weekAgo.toISOString())
      if (error) throw error
      return count ?? 0
    },
  })
}
