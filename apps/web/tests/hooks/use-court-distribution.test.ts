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
import { useCourtDistribution } from "@/lib/hooks/use-court-distribution"

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

describe("useCourtDistribution", () => {
  it("groups matches by court and sorts descending", async () => {
    const rows = [
      { judgments: { court: "Supreme Court of India" } },
      { judgments: { court: "Delhi High Court" } },
      { judgments: { court: "Supreme Court of India" } },
      { judgments: { court: "Supreme Court of India" } },
      { judgments: { court: "Delhi High Court" } },
      { judgments: { court: "Bombay High Court" } },
    ]
    const chain = mockChain(rows)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useCourtDistribution(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(supabase.from).toHaveBeenCalledWith("watch_matches")
    expect(chain.select).toHaveBeenCalledWith("judgments(court)")
    expect(chain.gte).toHaveBeenCalledWith("matched_at", expect.any(String))
    expect(result.current.data).toEqual([
      { court: "Supreme Court of India", count: 3 },
      { court: "Delhi High Court", count: 2 },
      { court: "Bombay High Court", count: 1 },
    ])
  })

  it("returns empty array for no data", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useCourtDistribution(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([])
  })

  it("handles null judgments as Unknown", async () => {
    const rows = [{ judgments: null }, { judgments: { court: "Delhi High Court" } }]
    const chain = mockChain(rows)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useCourtDistribution(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([
      { court: "Unknown", count: 1 },
      { court: "Delhi High Court", count: 1 },
    ])
  })

  it("handles error state", async () => {
    const chain = mockChain(null, { message: "Database error" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useCourtDistribution(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
