import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook } from "@testing-library/react"
import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

const channelMock = {
  on: vi.fn().mockReturnThis(),
  subscribe: vi.fn().mockReturnThis(),
}

vi.mock("@/lib/supabase/client", () => ({
  supabase: {
    channel: vi.fn(() => channelMock),
    removeChannel: vi.fn(),
    from: vi.fn(() => ({
      select: vi.fn().mockReturnThis(),
      order: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      then: vi.fn(),
    })),
  },
  createClient: vi.fn(),
}))

vi.mock("sonner", () => ({
  toast: {
    info: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import { supabase } from "@/lib/supabase/client"
import { toast } from "sonner"
import { RealtimeListener } from "@/components/layout/realtime-listener"

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    )
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  channelMock.on.mockReturnThis()
  channelMock.subscribe.mockReturnThis()
})

describe("RealtimeListener", () => {
  it("subscribes to watch_matches and watches channels on mount", () => {
    const wrapper = createWrapper()
    renderHook(() => RealtimeListener(), { wrapper })

    expect(supabase.channel).toHaveBeenCalledWith("watch_matches_changes")
    expect(supabase.channel).toHaveBeenCalledWith("watches_changes")
  })

  it("shows toast when new match arrives", () => {
    const wrapper = createWrapper()
    renderHook(() => RealtimeListener(), { wrapper })

    // Find the watch_matches INSERT callback
    const matchCall = channelMock.on.mock.calls.find(
      (call: any[]) =>
        call[0] === "postgres_changes" && call[1]?.event === "INSERT"
    )
    expect(matchCall).toBeDefined()
    const callback = matchCall![2]

    callback({ new: { id: "m1", snippet: "Test snippet" } })

    expect(toast.info).toHaveBeenCalledWith("New judgment matched", {
      description: "Test snippet",
    })
  })

  it("uses fallback description when snippet is null", () => {
    const wrapper = createWrapper()
    renderHook(() => RealtimeListener(), { wrapper })

    const matchCall = channelMock.on.mock.calls.find(
      (call: any[]) =>
        call[0] === "postgres_changes" && call[1]?.event === "INSERT"
    )
    const callback = matchCall![2]

    callback({ new: { id: "m1", snippet: null } })

    expect(toast.info).toHaveBeenCalledWith("New judgment matched", {
      description: "A new match was found by the polling worker.",
    })
  })

  it("unsubscribes from both channels on unmount", () => {
    const wrapper = createWrapper()
    const { unmount } = renderHook(() => RealtimeListener(), { wrapper })

    unmount()

    expect(supabase.removeChannel).toHaveBeenCalledTimes(2)
  })
})
