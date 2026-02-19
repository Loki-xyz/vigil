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
import {
  useActiveWatchCount,
  useMatchesToday,
  useMatchesThisWeek,
  useAlertsDeliveredCount,
} from "@/lib/hooks/use-dashboard"

function mockCountChain(
  resolvedCount: number | null,
  resolvedError: unknown = null
) {
  const result = Promise.resolve({ count: resolvedCount, error: resolvedError })
  const chain: any = {}
  for (const m of ["select", "eq", "gte", "lte", "order"]) {
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

describe("useActiveWatchCount", () => {
  it("returns count of active watches", async () => {
    const chain = mockCountChain(5)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useActiveWatchCount(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toBe(5)
    expect(supabase.from).toHaveBeenCalledWith("watches")
    expect(chain.eq).toHaveBeenCalledWith("is_active", true)
  })

  it("handles error state", async () => {
    const chain = mockCountChain(null, { message: "err" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useActiveWatchCount(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe("useMatchesToday", () => {
  it("returns count of matches today", async () => {
    const chain = mockCountChain(12)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useMatchesToday(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toBe(12)
    expect(supabase.from).toHaveBeenCalledWith("watch_matches")
    expect(chain.gte).toHaveBeenCalledWith("matched_at", expect.any(String))
  })

  it("handles error state", async () => {
    const chain = mockCountChain(null, { message: "err" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useMatchesToday(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe("useMatchesThisWeek", () => {
  it("returns count of matches this week", async () => {
    const chain = mockCountChain(42)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useMatchesThisWeek(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toBe(42)
    expect(supabase.from).toHaveBeenCalledWith("watch_matches")
    expect(chain.gte).toHaveBeenCalledWith("matched_at", expect.any(String))
  })

  it("handles error state", async () => {
    const chain = mockCountChain(null, { message: "err" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useMatchesThisWeek(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe("useAlertsDeliveredCount", () => {
  it("returns count of delivered alerts in last 7 days", async () => {
    const chain = mockCountChain(23)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useAlertsDeliveredCount(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toBe(23)
    expect(supabase.from).toHaveBeenCalledWith("notification_log")
    expect(chain.eq).toHaveBeenCalledWith("status", "sent")
    expect(chain.gte).toHaveBeenCalledWith("created_at", expect.any(String))
  })

  it("handles error state", async () => {
    const chain = mockCountChain(null, { message: "err" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useAlertsDeliveredCount(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
