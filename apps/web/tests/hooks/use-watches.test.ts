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
  useWatches,
  useWatch,
  useCreateWatch,
  useUpdateWatch,
  useDeleteWatch,
} from "@/lib/hooks/use-watches"

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

describe("useWatches", () => {
  it("fetches all watches", async () => {
    const watches = [
      { id: "w1", name: "Watch 1" },
      { id: "w2", name: "Watch 2" },
    ]
    const chain = mockChain(watches)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useWatches(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(watches)
    expect(supabase.from).toHaveBeenCalledWith("watches")
    expect(chain.select).toHaveBeenCalledWith("*")
  })

  it("orders by created_at descending", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useWatches(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chain.order).toHaveBeenCalledWith("created_at", {
      ascending: false,
    })
  })

  it("handles error state", async () => {
    const chain = mockChain(null, { message: "Database error" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useWatches(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe("useWatch", () => {
  it("fetches a single watch by id", async () => {
    const watch = { id: "w1", name: "Watch 1" }
    const chain = mockChain(watch)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useWatch("w1"), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(watch)
    expect(chain.eq).toHaveBeenCalledWith("id", "w1")
    expect(chain.single).toHaveBeenCalled()
  })

  it("handles not found error", async () => {
    const chain = mockChain(null, { message: "Not found" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useWatch("nonexistent"), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe("useCreateWatch", () => {
  it("inserts a new watch", async () => {
    const newWatch = { name: "New Watch", query: "test" }
    const chain = mockChain({ id: "w3", ...newWatch })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useCreateWatch(), {
      wrapper: createWrapper(),
    })

    result.current.mutate(newWatch as any)

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(supabase.from).toHaveBeenCalledWith("watches")
    expect(chain.insert).toHaveBeenCalled()
  })
})

describe("useUpdateWatch", () => {
  it("updates a watch", async () => {
    const chain = mockChain({ id: "w1", name: "Updated" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useUpdateWatch(), {
      wrapper: createWrapper(),
    })

    result.current.mutate({ id: "w1", name: "Updated" } as any)

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(supabase.from).toHaveBeenCalledWith("watches")
    expect(chain.update).toHaveBeenCalled()
    expect(chain.eq).toHaveBeenCalledWith("id", "w1")
  })
})

describe("useDeleteWatch", () => {
  it("deletes a watch", async () => {
    const chain = mockChain(null)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useDeleteWatch(), {
      wrapper: createWrapper(),
    })

    result.current.mutate("w1")

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(supabase.from).toHaveBeenCalledWith("watches")
    expect(chain.delete).toHaveBeenCalled()
    expect(chain.eq).toHaveBeenCalledWith("id", "w1")
  })
})
