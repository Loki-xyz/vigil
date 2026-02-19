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
  useSettings,
  useUpdateSetting,
  useClearMatchData,
  useResetSettings,
} from "@/lib/hooks/use-settings"

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

describe("useSettings", () => {
  it("fetches settings and returns key-value map", async () => {
    const rows = [
      { key: "k1", value: "v1" },
      { key: "k2", value: "v2" },
    ]
    const chain = mockChain(rows)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useSettings(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual({ k1: "v1", k2: "v2" })
    expect(supabase.from).toHaveBeenCalledWith("app_settings")
    expect(chain.select).toHaveBeenCalledWith("*")
  })

  it("handles error state", async () => {
    const chain = mockChain(null, { message: "Database error" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useSettings(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe("useUpdateSetting", () => {
  it("updates a setting by key", async () => {
    const chain = mockChain(null)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useUpdateSetting(), {
      wrapper: createWrapper(),
    })

    result.current.mutate({ key: "k1", value: "v1" })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(supabase.from).toHaveBeenCalledWith("app_settings")
    expect(chain.update).toHaveBeenCalled()
    expect(chain.eq).toHaveBeenCalledWith("key", "k1")
  })

  it("handles error state", async () => {
    const chain = mockChain(null, { message: "Update failed" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useUpdateSetting(), {
      wrapper: createWrapper(),
    })

    result.current.mutate({ key: "k1", value: "v1" })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe("useClearMatchData", () => {
  it("deletes from watch_matches and judgments, resets watch counts", async () => {
    const chain = mockChain(null)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useClearMatchData(), {
      wrapper: createWrapper(),
    })

    result.current.mutate(undefined)

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(supabase.from).toHaveBeenCalledWith("watch_matches")
    expect(supabase.from).toHaveBeenCalledWith("judgments")
    expect(supabase.from).toHaveBeenCalledWith("watches")
    expect(chain.delete).toHaveBeenCalled()
    expect(chain.update).toHaveBeenCalledWith({
      last_poll_result_count: 0,
      last_polled_at: null,
    })
    expect(chain.neq).toHaveBeenCalledWith(
      "id",
      "00000000-0000-0000-0000-000000000000"
    )
  })

  it("handles error state", async () => {
    const chain = mockChain(null, { message: "Delete failed" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useClearMatchData(), {
      wrapper: createWrapper(),
    })

    result.current.mutate(undefined)

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe("useResetSettings", () => {
  it("resets all settings to defaults", async () => {
    const chain = mockChain(null)
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useResetSettings(), {
      wrapper: createWrapper(),
    })

    result.current.mutate(undefined)

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(supabase.from).toHaveBeenCalledWith("app_settings")
    // Should be called 8 times (once per default setting)
    expect(supabase.from).toHaveBeenCalledTimes(8)
    expect(chain.update).toHaveBeenCalled()
    expect(chain.eq).toHaveBeenCalledWith("key", "notification_email_enabled")
    expect(chain.eq).toHaveBeenCalledWith("key", "notification_slack_enabled")
    expect(chain.eq).toHaveBeenCalledWith(
      "key",
      "notification_email_recipients"
    )
    expect(chain.eq).toHaveBeenCalledWith(
      "key",
      "notification_slack_webhook_url"
    )
    expect(chain.eq).toHaveBeenCalledWith("key", "default_court_filter")
    expect(chain.eq).toHaveBeenCalledWith("key", "global_polling_enabled")
    expect(chain.eq).toHaveBeenCalledWith("key", "daily_digest_enabled")
    expect(chain.eq).toHaveBeenCalledWith("key", "daily_digest_time")
  })

  it("handles error state", async () => {
    const chain = mockChain(null, { message: "Reset failed" })
    vi.mocked(supabase.from).mockReturnValue(chain)

    const { result } = renderHook(() => useResetSettings(), {
      wrapper: createWrapper(),
    })

    result.current.mutate(undefined)

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
