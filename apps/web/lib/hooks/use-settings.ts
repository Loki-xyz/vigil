"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { supabase } from "@/lib/supabase/client"

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("app_settings")
        .select("*")
      if (error) throw error
      const map: Record<string, string> = {}
      for (const row of data ?? []) {
        map[row.key] = row.value
      }
      return map
    },
  })
}

export function useUpdateSetting() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ key, value }: { key: string; value: string }) => {
      const { error } = await supabase
        .from("app_settings")
        .update({ value, updated_at: new Date().toISOString() })
        .eq("key", key)
      if (error) throw error
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] })
    },
  })
}

export function useClearMatchData() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { error: matchError } = await supabase
        .from("watch_matches")
        .delete()
        .neq("id", "00000000-0000-0000-0000-000000000000")
      if (matchError) throw matchError
      const { error: judgError } = await supabase
        .from("judgments")
        .delete()
        .neq("id", "00000000-0000-0000-0000-000000000000")
      if (judgError) throw judgError
      const { error: watchError } = await supabase
        .from("watches")
        .update({ last_poll_result_count: 0, last_polled_at: null })
        .neq("id", "00000000-0000-0000-0000-000000000000")
      if (watchError) throw watchError
    },
    onSuccess: () => {
      queryClient.invalidateQueries()
    },
  })
}

export function useResetSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const defaults = [
        { key: "notification_email_enabled", value: "true" },
        { key: "notification_slack_enabled", value: "false" },
        { key: "notification_email_recipients", value: "" },
        { key: "notification_slack_webhook_url", value: "" },
        { key: "default_court_filter", value: "" },
        { key: "global_polling_enabled", value: "true" },
        { key: "daily_digest_enabled", value: "true" },
        { key: "daily_digest_time", value: "09:00" },
      ]
      for (const { key, value } of defaults) {
        const { error } = await supabase
          .from("app_settings")
          .update({ value, updated_at: new Date().toISOString() })
          .eq("key", key)
        if (error) throw error
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] })
    },
  })
}
