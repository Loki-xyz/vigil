"use client"

import { useQuery } from "@tanstack/react-query"
import { supabase } from "@/lib/supabase/client"
import type { Judgment } from "@/lib/supabase/types"

export interface JudgmentFilters {
  court?: string
  dateFrom?: string
  dateTo?: string
  search?: string
}

export interface JudgmentWithMatchCount extends Judgment {
  watch_matches: { count: number }[]
}

export function useJudgments(filters?: JudgmentFilters) {
  return useQuery({
    queryKey: ["judgments", filters],
    queryFn: async () => {
      let query = supabase
        .from("judgments")
        .select("*, watch_matches(count)")
        .order("judgment_date", { ascending: false })

      if (filters?.court) {
        query = query.eq("court", filters.court)
      }
      if (filters?.dateFrom) {
        query = query.gte("judgment_date", filters.dateFrom)
      }
      if (filters?.dateTo) {
        query = query.lte("judgment_date", filters.dateTo)
      }
      if (filters?.search) {
        query = query.ilike("title", `%${filters.search}%`)
      }

      const { data, error } = await query
      if (error) throw error
      return data as JudgmentWithMatchCount[]
    },
  })
}
