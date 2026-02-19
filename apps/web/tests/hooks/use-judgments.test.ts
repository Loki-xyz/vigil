import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import React from "react"

vi.mock("@/lib/supabase/client", () => ({
  supabase: { from: vi.fn() },
  createClient: vi.fn(),
}))

import { supabase } from "@/lib/supabase/client"
import { useJudgments } from "@/lib/hooks/use-judgments"

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
    "ilike",
    "order",
    "single",
    "limit",
    "range",
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

describe("useJudgments", () => {
  it("fetches judgments with no filters", async () => {
    const judgments = [{ id: "j1", title: "Judgment 1" }]
    const chain = mockChain(judgments)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useJudgments({}), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(supabase.from).toHaveBeenCalledWith("judgments")
    expect(chain.select).toHaveBeenCalled()
    expect(chain.order).toHaveBeenCalled()
  })

  it("applies court filter", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(
      () => useJudgments({ court: "Delhi High Court" }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chain.eq).toHaveBeenCalledWith("court", "Delhi High Court")
  })

  it("applies dateFrom filter", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(
      () => useJudgments({ dateFrom: "2026-02-01" }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chain.gte).toHaveBeenCalledWith("judgment_date", "2026-02-01")
  })

  it("applies dateTo filter", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(
      () => useJudgments({ dateTo: "2026-02-28" }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chain.lte).toHaveBeenCalledWith("judgment_date", "2026-02-28")
  })

  it("applies search filter", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(
      () => useJudgments({ search: "Amazon" }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chain.ilike).toHaveBeenCalledWith("title", "%Amazon%")
  })

  it("applies combined filters", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(
      () =>
        useJudgments({
          court: "Delhi High Court",
          dateFrom: "2026-02-01",
          dateTo: "2026-02-28",
          search: "Amazon",
        }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chain.eq).toHaveBeenCalledWith("court", "Delhi High Court")
    expect(chain.gte).toHaveBeenCalledWith("judgment_date", "2026-02-01")
    expect(chain.lte).toHaveBeenCalledWith("judgment_date", "2026-02-28")
    expect(chain.ilike).toHaveBeenCalledWith("title", "%Amazon%")
  })

  it("uses different query keys for different filters", async () => {
    const chain1 = mockChain([{ id: "j1" }])
    const chain2 = mockChain([{ id: "j2" }])

    vi.mocked(supabase.from).mockReturnValueOnce(chain1)

    const wrapper = createWrapper()
    const { result: result1 } = renderHook(
      () => useJudgments({ court: "Delhi High Court" }),
      { wrapper }
    )

    await waitFor(() => expect(result1.current.isSuccess).toBe(true))

    vi.mocked(supabase.from).mockReturnValueOnce(chain2)

    const { result: result2 } = renderHook(
      () => useJudgments({ court: "Bombay High Court" }),
      { wrapper }
    )

    await waitFor(() => expect(result2.current.isSuccess).toBe(true))

    // Different filters should trigger separate fetches
    expect(supabase.from).toHaveBeenCalledTimes(2)
  })
})
