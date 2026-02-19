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
import { useNotifications } from "@/lib/hooks/use-notifications"

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

describe("useNotifications", () => {
  it("fetches from notification_log with joined select and orders by created_at desc", async () => {
    const notifications = [
      {
        id: "n1",
        channel: "email",
        status: "sent",
        created_at: "2026-02-19T10:00:00Z",
        watch_matches: null,
      },
    ]
    const chain = mockChain(notifications)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useNotifications(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(notifications)
    expect(supabase.from).toHaveBeenCalledWith("notification_log")
    expect(chain.select).toHaveBeenCalledWith(
      "*, watch_matches(watch_id, watches(name))"
    )
    expect(chain.order).toHaveBeenCalledWith("created_at", {
      ascending: false,
    })
  })

  it("applies channel filter", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(
      () => useNotifications({ channel: "email" as any }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chain.eq).toHaveBeenCalledWith("channel", "email")
  })

  it("applies status filter", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(
      () => useNotifications({ status: "sent" as any }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chain.eq).toHaveBeenCalledWith("status", "sent")
  })

  it("applies dateFrom filter", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(
      () => useNotifications({ dateFrom: "2026-01-01" }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chain.gte).toHaveBeenCalledWith("created_at", "2026-01-01")
  })

  it("applies dateTo filter", async () => {
    const chain = mockChain([])
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(
      () => useNotifications({ dateTo: "2026-02-01" }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(chain.lte).toHaveBeenCalledWith("created_at", "2026-02-01")
  })
})
