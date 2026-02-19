import { vi } from "vitest"
import type { Watch, Judgment } from "@/lib/supabase/types"

// Sample test data
export const sampleWatches: Watch[] = [
  {
    id: "w1",
    name: "AWS Judgments",
    watch_type: "entity",
    query_terms: "Amazon Web Services",
    query_template: null,
    court_filter: ["supremecourt", "delhi"],
    is_active: true,
    polling_interval_minutes: 120,
    last_polled_at: "2026-02-17T10:00:00+00:00",
    last_poll_result_count: 3,
    created_at: "2026-02-01T00:00:00+00:00",
    updated_at: "2026-02-17T10:00:00+00:00",
  },
  {
    id: "w2",
    name: "DTAA Mauritius",
    watch_type: "topic",
    query_terms: "India Mauritius DTAA",
    query_template: null,
    court_filter: ["supremecourt"],
    is_active: true,
    polling_interval_minutes: 240,
    last_polled_at: null,
    last_poll_result_count: 0,
    created_at: "2026-02-10T00:00:00+00:00",
    updated_at: "2026-02-10T00:00:00+00:00",
  },
]

export const sampleJudgments: Judgment[] = [
  {
    id: "j1",
    ik_doc_id: 12345678,
    title: "Amazon Web Services Inc. vs Commissioner of Income Tax",
    court: "Delhi High Court",
    judgment_date: "2026-02-17",
    headline: "Cloud computing services taxation",
    doc_size: 24000,
    num_cites: 5,
    ik_url: "https://indiankanoon.org/doc/12345678/",
    metadata_json: {},
    first_seen_at: "2026-02-17T12:00:00+00:00",
    created_at: "2026-02-17T12:00:00+00:00",
  },
]

/**
 * Creates a chainable mock that mimics the Supabase PostgREST query builder.
 */
function createChainableMock(resolvedData: unknown[] = []) {
  const mock: Record<string, unknown> = {}
  const chainMethods = [
    "select",
    "insert",
    "update",
    "upsert",
    "delete",
    "eq",
    "neq",
    "lt",
    "lte",
    "gte",
    "is",
    "in",
    "ilike",
    "order",
    "limit",
    "single",
  ]

  for (const method of chainMethods) {
    mock[method] = vi.fn().mockReturnValue(mock)
  }

  // Terminal methods
  mock.then = undefined // Make it non-thenable until explicitly awaited
  mock.data = resolvedData
  mock.error = null

  return mock
}

/**
 * Creates a fully mocked Supabase client.
 */
export function createMockSupabaseClient(overrides?: {
  watches?: Watch[]
  judgments?: Judgment[]
}) {
  const watches = overrides?.watches ?? sampleWatches
  const judgments = overrides?.judgments ?? sampleJudgments

  const fromMock = vi.fn().mockImplementation((table: string) => {
    switch (table) {
      case "watches":
        return createChainableMock(watches)
      case "judgments":
        return createChainableMock(judgments)
      default:
        return createChainableMock([])
    }
  })

  const channelMock = vi.fn().mockReturnValue({
    on: vi.fn().mockReturnThis(),
    subscribe: vi.fn().mockReturnThis(),
  })

  return {
    from: fromMock,
    channel: channelMock,
    removeChannel: vi.fn(),
  }
}
