"use client"

import { useQuery } from "@tanstack/react-query"
import { startOfDay, subDays } from "date-fns"
import { toZonedTime, fromZonedTime } from "date-fns-tz"
import { supabase } from "@/lib/supabase/client"

const IST = "Asia/Kolkata"

/** Get IST midnight as a UTC ISO string (for DB queries). */
function istMidnight(daysAgo = 0): string {
  const istNow = toZonedTime(new Date(), IST)
  const istDay = subDays(startOfDay(istNow), daysAgo)
  return fromZonedTime(istDay, IST).toISOString()
}

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
      const { count, error } = await supabase
        .from("watch_matches")
        .select("*", { count: "exact", head: true })
        .gte("matched_at", istMidnight())
      if (error) throw error
      return count ?? 0
    },
  })
}

export function useMatchesThisWeek() {
  return useQuery({
    queryKey: ["dashboard", "matches-week"],
    queryFn: async () => {
      const { count, error } = await supabase
        .from("watch_matches")
        .select("*", { count: "exact", head: true })
        .gte("matched_at", istMidnight(7))
      if (error) throw error
      return count ?? 0
    },
  })
}

export function useAlertsDeliveredCount() {
  return useQuery({
    queryKey: ["dashboard", "alerts-delivered-7d"],
    queryFn: async () => {
      const { count, error } = await supabase
        .from("notification_log")
        .select("*", { count: "exact", head: true })
        .eq("status", "sent")
        .gte("created_at", istMidnight(7))
      if (error) throw error
      return count ?? 0
    },
  })
}
