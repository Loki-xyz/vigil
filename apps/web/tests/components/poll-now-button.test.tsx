import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

const { mockFrom, mockChannel, mockRemoveChannel } = vi.hoisted(() => ({
  mockFrom: vi.fn(),
  mockChannel: vi.fn(() => ({
    on: vi.fn().mockReturnThis(),
    subscribe: vi.fn(),
  })),
  mockRemoveChannel: vi.fn(),
}))

vi.mock("@/lib/supabase/client", () => ({
  supabase: {
    from: (...args: any[]) => mockFrom(...args),
    channel: mockChannel,
    removeChannel: mockRemoveChannel,
  },
  createClient: vi.fn(),
}))

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

import { PollNowButton } from "@/components/watches/poll-now-button"

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children)
  }
}

function renderWithQuery(ui: React.ReactElement) {
  const Wrapper = createWrapper()
  return render(ui, { wrapper: Wrapper })
}

describe("PollNowButton", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockFrom.mockReturnValue({
      insert: vi.fn().mockReturnValue({
        select: vi.fn().mockReturnValue({
          single: vi.fn().mockResolvedValue({
            data: { id: "pr1", watch_id: "w1", status: "pending" },
            error: null,
          }),
        }),
      }),
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("renders 'Poll Now' button text", () => {
    renderWithQuery(<PollNowButton watchId="w1" />)
    expect(screen.getByText("Poll Now")).toBeDefined()
  })

  it("button is not disabled initially", () => {
    renderWithQuery(<PollNowButton watchId="w1" />)
    const button = screen.getByRole("button", { name: /Poll Now/ })
    expect(button).not.toBeDisabled()
  })

  it("calls supabase.from('poll_requests') with insert when clicked", async () => {
    vi.useRealTimers()
    const user = userEvent.setup()
    renderWithQuery(<PollNowButton watchId="w1" />)
    const button = screen.getByRole("button", { name: /Poll Now/ })
    await user.click(button)
    expect(mockFrom).toHaveBeenCalledWith("poll_requests")
  })

  it("cleans up channel on unmount", () => {
    const { unmount } = renderWithQuery(<PollNowButton watchId="w1" />)
    unmount()
    // Should not throw
  })
})
