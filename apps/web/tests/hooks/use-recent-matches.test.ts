import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import React from "react"

vi.mock("@/lib/supabase/client", () => {
  const mockFrom = vi.fn()
  return {
    supabase: { from: mockFrom },
    createClient: vi.fn(),
  }
})

import { supabase } from "@/lib/supabase/client"
import { useRecentMatches } from "@/lib/hooks/use-recent-matches"

function mockChain(resolvedData: unknown, resolvedError: unknown = null) {
  const result = Promise.resolve({ data: resolvedData, error: resolvedError })
  const chain: any = {}
  for (const m of [
    "select",
    "insert",
    "update",
    "delete",
    "eq",
    "neq",
    "gte",
    "lte",
    "order",
    "single",
    "limit",
  ]) {
    chain[m] = vi.fn().mockReturnValue(chain)
  }
  chain.then = result.then.bind(result)
  chain.catch = result.catch.bind(result)
  return chain
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children
    )
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe("useRecentMatches", () => {
  it("fetches recent matches with joins, ordered by matched_at desc, limit 10", async () => {
    const matches = [
      {
        id: "m1",
        watch_id: "w1",
        judgment_id: "j1",
        matched_at: "2026-02-19T10:00:00Z",
        judgments: { id: "j1", title: "Test Judgment" },
        watches: { name: "Test Watch" },
      },
    ]
    const chain = mockChain(matches)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useRecentMatches(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(matches)
    expect(supabase.from).toHaveBeenCalledWith("watch_matches")
    expect(chain.select).toHaveBeenCalledWith(
      "*, judgments(*), watches(name)"
    )
    expect(chain.order).toHaveBeenCalledWith("matched_at", {
      ascending: false,
    })
    expect(chain.limit).toHaveBeenCalledWith(10)
  })

  it("accepts custom limit parameter", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useRecentMatches(5), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chain.limit).toHaveBeenCalledWith(5)
  })

  it("handles error state", async () => {
    const chain = mockChain(null, { message: "Database error" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useRecentMatches(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
