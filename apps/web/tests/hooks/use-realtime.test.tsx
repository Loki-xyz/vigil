import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook } from "@testing-library/react"

const channelMock = {
  on: vi.fn().mockReturnThis(),
  subscribe: vi.fn().mockReturnThis(),
}

vi.mock("@/lib/supabase/client", () => ({
  supabase: {
    channel: vi.fn(() => channelMock),
    removeChannel: vi.fn(),
  },
  createClient: vi.fn(),
}))

import { supabase } from "@/lib/supabase/client"
import {
  useRealtimeMatches,
  useRealtimeWatches,
} from "@/lib/hooks/use-realtime"

beforeEach(() => {
  vi.clearAllMocks()
  channelMock.on.mockReturnThis()
  channelMock.subscribe.mockReturnThis()
})

describe("useRealtimeMatches", () => {
  it("subscribes on mount", () => {
    const onNewMatch = vi.fn()
    renderHook(() => useRealtimeMatches(onNewMatch))

    expect(supabase.channel).toHaveBeenCalled()
    expect(channelMock.on).toHaveBeenCalledWith(
      "postgres_changes",
      expect.objectContaining({
        event: "INSERT",
        table: "watch_matches",
      }),
      expect.any(Function)
    )
    expect(channelMock.subscribe).toHaveBeenCalled()
  })

  it("fires callback when new match arrives", () => {
    const onNewMatch = vi.fn()
    renderHook(() => useRealtimeMatches(onNewMatch))

    // Extract the callback passed to on()
    const onCall = channelMock.on.mock.calls.find(
      (call: any[]) =>
        call[0] === "postgres_changes" && call[1]?.event === "INSERT"
    )
    const callback = onCall![2]

    const matchData = { id: "m1", watch_id: "w1", judgment_id: "j1" }
    callback({ new: matchData })

    expect(onNewMatch).toHaveBeenCalledWith(matchData)
  })

  it("unsubscribes on unmount", () => {
    const onNewMatch = vi.fn()
    const { unmount } = renderHook(() => useRealtimeMatches(onNewMatch))

    unmount()

    expect(supabase.removeChannel).toHaveBeenCalled()
  })
})

describe("useRealtimeWatches", () => {
  it("subscribes to all watch events", () => {
    const onUpdate = vi.fn()
    renderHook(() => useRealtimeWatches(onUpdate))

    expect(supabase.channel).toHaveBeenCalled()
    expect(channelMock.on).toHaveBeenCalledWith(
      "postgres_changes",
      expect.objectContaining({
        event: "*",
        table: "watches",
      }),
      expect.any(Function)
    )
    expect(channelMock.subscribe).toHaveBeenCalled()
  })

  it("fires callback when watch event occurs", () => {
    const onUpdate = vi.fn()
    renderHook(() => useRealtimeWatches(onUpdate))

    const onCall = channelMock.on.mock.calls.find(
      (call: any[]) =>
        call[0] === "postgres_changes" && call[1]?.table === "watches"
    )
    const callback = onCall![2]

    callback({ new: { id: "w1", name: "Updated Watch" } })

    expect(onUpdate).toHaveBeenCalled()
  })
})
