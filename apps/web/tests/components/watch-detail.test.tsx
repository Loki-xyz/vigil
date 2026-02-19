import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

// Mock hooks
const mockUseWatch = vi.fn()
const mockUseUpdateWatch = vi.fn()
const mockUseWatchMatches = vi.fn()
const mockUseWatchApiLog = vi.fn()

vi.mock("@/lib/hooks/use-watches", () => ({
  useWatch: (id: string) => mockUseWatch(id),
  useUpdateWatch: () => mockUseUpdateWatch(),
  useWatchMatches: (id: string) => mockUseWatchMatches(id),
  useWatchApiLog: (id: string) => mockUseWatchApiLog(id),
}))

// Mock child components
vi.mock("@/components/watches/watch-form", () => ({
  WatchForm: () => <div data-testid="watch-form" />,
}))

vi.mock("@/components/watches/poll-now-button", () => ({
  PollNowButton: () => <div data-testid="poll-now-button" />,
}))

vi.mock("@/components/watches/watch-type-badge", () => ({
  WatchTypeBadge: ({ type }: { type: string }) => <span data-testid="watch-type-badge">{type}</span>,
  StatusBadge: ({ isActive }: { isActive: boolean }) => (
    <span data-testid="status-badge">{isActive ? "Active" : "Paused"}</span>
  ),
}))

vi.mock("@/components/judgments/court-badge", () => ({
  CourtBadge: ({ court }: { court: string | null }) => (
    <span data-testid="court-badge">{court ?? "—"}</span>
  ),
}))

vi.mock("@/components/ui/data-table", () => ({
  DataTable: ({ table }: any) => <div data-testid="data-table" />,
}))

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

import { WatchDetail } from "@/components/watches/watch-detail"

const mockWatch = {
  id: "w1",
  name: "Test Watch",
  watch_type: "entity",
  query_terms: "test",
  court_filter: [],
  is_active: true,
  polling_interval_minutes: 120,
  last_polled_at: null,
  last_poll_result_count: 0,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
}

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

describe("WatchDetail", () => {
  beforeEach(() => {
    mockUseWatch.mockReturnValue({ data: mockWatch, isLoading: false })
    mockUseUpdateWatch.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseWatchMatches.mockReturnValue({ data: [], isLoading: false })
    mockUseWatchApiLog.mockReturnValue({ data: [], isLoading: false })
  })

  it("shows loading skeleton when isLoading is true", () => {
    mockUseWatch.mockReturnValue({ data: undefined, isLoading: true })
    const { container } = renderWithQuery(<WatchDetail id="w1" />)
    const skeletons = container.querySelectorAll("[data-slot='skeleton']")
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it("shows 'Watch not found.' when watch is null and not loading", () => {
    mockUseWatch.mockReturnValue({ data: undefined, isLoading: false })
    renderWithQuery(<WatchDetail id="w1" />)
    expect(screen.getByText("Watch not found.")).toBeDefined()
  })

  it("shows watch name when loaded", () => {
    renderWithQuery(<WatchDetail id="w1" />)
    expect(screen.getByText("Test Watch")).toBeDefined()
  })

  it("shows 'Matched Judgments' and 'Poll History' tab triggers", () => {
    renderWithQuery(<WatchDetail id="w1" />)
    expect(screen.getByText(/Matched Judgments/)).toBeDefined()
    expect(screen.getByText(/Poll History/)).toBeDefined()
  })
})
