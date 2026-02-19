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
import { useMatchTrend } from "@/lib/hooks/use-match-trend"

function mockChain(resolvedData: unknown, resolvedError: unknown = null) {
  const result = Promise.resolve({ data: resolvedData, error: resolvedError })
  const chain: any = {}
  for (const m of ["select", "eq", "gte", "lte", "order", "limit"]) {
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

describe("useMatchTrend", () => {
  it("groups matches by date", async () => {
    const rows = [
      { matched_at: "2026-02-15T10:00:00Z" },
      { matched_at: "2026-02-15T14:00:00Z" },
      { matched_at: "2026-02-16T09:00:00Z" },
    ]
    const chain = mockChain(rows)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useMatchTrend(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(supabase.from).toHaveBeenCalledWith("watch_matches")
    expect(chain.select).toHaveBeenCalledWith("matched_at")
    expect(chain.gte).toHaveBeenCalledWith("matched_at", expect.any(String))
    expect(chain.order).toHaveBeenCalledWith("matched_at", {
      ascending: true,
    })
    expect(result.current.data).toHaveLength(2)
    expect(result.current.data![0]).toEqual({ date: "Feb 15", matches: 2 })
    expect(result.current.data![1]).toEqual({ date: "Feb 16", matches: 1 })
  })

  it("returns empty array for no data", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useMatchTrend(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([])
  })

  it("handles error state", async () => {
    const chain = mockChain(null, { message: "Database error" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useMatchTrend(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
