"use client"

import { useQuery } from "@tanstack/react-query"
import { supabase } from "@/lib/supabase/client"
import type { NotificationChannel, NotificationStatus } from "@/lib/supabase/types"

export interface NotificationFilters {
  channel?: NotificationChannel
  status?: NotificationStatus
  dateFrom?: string
  dateTo?: string
}

export interface NotificationWithWatch {
  id: string
  watch_match_id: string | null
  channel: NotificationChannel
  recipient: string
  status: NotificationStatus
  error_message: string | null
  sent_at: string | null
  retry_count: number
  created_at: string
  watch_matches: {
    watch_id: string
    watches: { name: string } | null
  } | null
}

export function useNotifications(filters?: NotificationFilters) {
  return useQuery({
    queryKey: ["notifications", filters],
    queryFn: async () => {
      let query = supabase
        .from("notification_log")
        .select("*, watch_matches(watch_id, watches(name))")
        .order("created_at", { ascending: false })

      if (filters?.channel) {
        query = query.eq("channel", filters.channel)
      }
      if (filters?.status) {
        query = query.eq("status", filters.status)
      }
      if (filters?.dateFrom) {
        query = query.gte("created_at", filters.dateFrom)
      }
      if (filters?.dateTo) {
        query = query.lte("created_at", filters.dateTo)
      }

      const { data, error } = await query
      if (error) throw error
      return data as NotificationWithWatch[]
    },
  })
}
