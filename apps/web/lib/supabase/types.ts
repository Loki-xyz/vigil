export type WatchType = "entity" | "topic" | "act"

export interface Watch {
  id: string
  name: string
  watch_type: WatchType
  query_terms: string
  query_template: string | null
  court_filter: string[]
  is_active: boolean
  polling_interval_minutes: number
  last_polled_at: string | null
  last_poll_result_count: number
  created_at: string
  updated_at: string
}

export interface Judgment {
  id: string
  ik_doc_id: number
  title: string
  court: string | null
  judgment_date: string | null
  headline: string | null
  doc_size: number | null
  num_cites: number
  ik_url: string
  metadata_json: Record<string, unknown>
  first_seen_at: string
  created_at: string
}

export interface WatchMatch {
  id: string
  watch_id: string
  judgment_id: string
  matched_at: string
  relevance_score: number | null
  snippet: string | null
  is_notified: boolean
  notified_at: string | null
  // Joined relations (optional)
  watches?: Watch
  judgments?: Judgment
}

export type NotificationChannel = "email" | "slack"
export type NotificationStatus = "pending" | "sent" | "failed" | "retrying"

export interface NotificationLogEntry {
  id: string
  watch_match_id: string | null
  channel: NotificationChannel
  recipient: string
  status: NotificationStatus
  error_message: string | null
  sent_at: string | null
  retry_count: number
  created_at: string
}

export interface ApiCallLogEntry {
  id: string
  endpoint: string
  request_url: string
  watch_id: string | null
  http_status: number | null
  result_count: number | null
  response_time_ms: number | null
  error_message: string | null
  created_at: string
}

export interface AppSetting {
  key: string
  value: string
  description: string | null
  updated_at: string
}

export type PollRequestStatus = "pending" | "processing" | "done" | "failed"

export interface PollRequest {
  id: string
  watch_id: string
  status: PollRequestStatus
  created_at: string
}
