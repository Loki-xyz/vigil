"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { supabase } from "@/lib/supabase/client"
import type { Watch, WatchMatch, ApiCallLogEntry } from "@/lib/supabase/types"

export function useWatches() {
  return useQuery({
    queryKey: ["watches"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("watches")
        .select("*")
        .order("created_at", { ascending: false })
      if (error) throw error
      return data as Watch[]
    },
  })
}

export function useWatch(id: string) {
  return useQuery({
    queryKey: ["watches", id],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("watches")
        .select("*")
        .eq("id", id)
        .single()
      if (error) throw error
      return data as Watch
    },
  })
}

export function useCreateWatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (watch: Partial<Watch>) => {
      const { data, error } = await supabase
        .from("watches")
        .insert(watch)
        .select()
        .single()
      if (error) throw error
      return data as Watch
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watches"] })
    },
  })
}

export function useUpdateWatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...updates }: Partial<Watch> & { id: string }) => {
      const { data, error } = await supabase
        .from("watches")
        .update(updates)
        .eq("id", id)
        .select()
        .single()
      if (error) throw error
      return data as Watch
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["watches"] })
      queryClient.invalidateQueries({ queryKey: ["watches", data.id] })
    },
  })
}

export function useDeleteWatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { error } = await supabase.from("watches").delete().eq("id", id)
      if (error) throw error
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watches"] })
    },
  })
}

export function useWatchMatches(watchId: string) {
  return useQuery({
    queryKey: ["watches", watchId, "matches"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("watch_matches")
        .select("*, judgments(*)")
        .eq("watch_id", watchId)
        .order("matched_at", { ascending: false })
      if (error) throw error
      return data as WatchMatch[]
    },
    enabled: !!watchId,
  })
}

export function useWatchApiLog(watchId: string) {
  return useQuery({
    queryKey: ["watches", watchId, "api-log"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("api_call_log")
        .select("*")
        .eq("watch_id", watchId)
        .order("created_at", { ascending: false })
      if (error) throw error
      return data as ApiCallLogEntry[]
    },
    enabled: !!watchId,
  })
}
