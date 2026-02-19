import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

// Mock hooks
const mockUseWatches = vi.fn()
const mockUseCreateWatch = vi.fn()

vi.mock("@/lib/hooks/use-watches", () => ({
  useWatches: () => mockUseWatches(),
  useCreateWatch: () => mockUseCreateWatch(),
}))

// Mock child components
vi.mock("@/components/layout/header", () => ({
  Header: ({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) => (
    <div data-testid="header">
      <h1>{title}</h1>
      {description && <p>{description}</p>}
      {actions}
    </div>
  ),
}))

vi.mock("@/components/ui/data-table", () => ({
  DataTable: ({ table }: any) => (
    <div data-testid="data-table">
      {table.getRowModel().rows.length} rows
    </div>
  ),
}))

vi.mock("@/components/watches/watch-form", () => ({
  WatchForm: () => <div data-testid="watch-form" />,
}))

vi.mock("@/components/watches/watch-columns", () => ({
  watchColumns: [],
}))

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

import { WatchesContent } from "@/components/watches/watches-content"

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

describe("WatchesContent", () => {
  beforeEach(() => {
    mockUseWatches.mockReturnValue({ data: [], isLoading: false })
    mockUseCreateWatch.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  })

  it("shows 'Watches' heading via Header", () => {
    renderWithQuery(<WatchesContent />)
    expect(screen.getByText("Watches")).toBeDefined()
  })

  it("shows loading skeletons when isLoading is true", () => {
    mockUseWatches.mockReturnValue({ data: undefined, isLoading: true })
    const { container } = renderWithQuery(<WatchesContent />)
    const skeletons = container.querySelectorAll("[data-slot='skeleton']")
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it("shows DataTable when loaded with watches", () => {
    mockUseWatches.mockReturnValue({
      data: [{ id: "w1", name: "Test" }],
      isLoading: false,
    })
    renderWithQuery(<WatchesContent />)
    expect(screen.getByTestId("data-table")).toBeDefined()
  })

  it("renders 'New Watch' button", () => {
    renderWithQuery(<WatchesContent />)
    expect(screen.getByText("New Watch")).toBeDefined()
  })

  it("has dialog container with 'Create New Watch' title", async () => {
    const user = userEvent.setup()
    renderWithQuery(<WatchesContent />)
    const newWatchButton = screen.getByText("New Watch")
    await user.click(newWatchButton)
    expect(screen.getByText("Create New Watch")).toBeDefined()
  })
})
