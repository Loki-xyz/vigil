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
import { useTopWatches } from "@/lib/hooks/use-top-watches"

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

describe("useTopWatches", () => {
  it("groups by watch name, sorts descending, limits to 5", async () => {
    const rows = [
      { watches: { name: "SEBI enforcement" } },
      { watches: { name: "SEBI enforcement" } },
      { watches: { name: "SEBI enforcement" } },
      { watches: { name: "Arbitration s.34" } },
      { watches: { name: "Arbitration s.34" } },
      { watches: { name: "Tax tribunals" } },
    ]
    const chain = mockChain(rows)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useTopWatches(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(supabase.from).toHaveBeenCalledWith("watch_matches")
    expect(chain.select).toHaveBeenCalledWith("watches(name)")
    expect(chain.gte).toHaveBeenCalledWith("matched_at", expect.any(String))
    expect(result.current.data).toEqual([
      { name: "SEBI enforcement", value: 3 },
      { name: "Arbitration s.34", value: 2 },
      { name: "Tax tribunals", value: 1 },
    ])
  })

  it("limits results to specified count", async () => {
    const rows = Array.from({ length: 20 }, (_, i) => ({
      watches: { name: `Watch ${i}` },
    }))
    const chain = mockChain(rows)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useTopWatches(30, 3), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(3)
  })

  it("returns empty array for no data", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useTopWatches(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([])
  })

  it("handles null watches as Unknown", async () => {
    const rows = [{ watches: null }, { watches: { name: "Tax tribunals" } }]
    const chain = mockChain(rows)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useTopWatches(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([
      { name: "Unknown", value: 1 },
      { name: "Tax tribunals", value: 1 },
    ])
  })

  it("handles error state", async () => {
    const chain = mockChain(null, { message: "Database error" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useTopWatches(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
