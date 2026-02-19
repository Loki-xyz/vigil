import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

const mockUseNotifications = vi.fn()

vi.mock("@/lib/hooks/use-notifications", () => ({
  useNotifications: (filters?: any) => mockUseNotifications(filters),
}))

vi.mock("@/components/ui/data-table", () => ({
  DataTable: ({ table }: any) => (
    <div data-testid="data-table">
      {table.getRowModel().rows.length} rows
    </div>
  ),
}))

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

import { NotificationTable } from "@/components/alerts/notification-table"

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

describe("NotificationTable", () => {
  beforeEach(() => {
    mockUseNotifications.mockReturnValue({ data: [], isLoading: false })
  })

  it("shows loading skeletons when isLoading is true", () => {
    mockUseNotifications.mockReturnValue({ data: undefined, isLoading: true })
    const { container } = renderWithQuery(<NotificationTable />)
    const skeletons = container.querySelectorAll("[data-slot='skeleton']")
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it("renders filter selects and 2 date inputs", () => {
    renderWithQuery(<NotificationTable />)
    expect(screen.getByText("All Channels")).toBeDefined()
    expect(screen.getByText("All Statuses")).toBeDefined()
    const dateInputs = screen.getAllByDisplayValue("")
    const dateTypeInputs = dateInputs.filter(
      (el) => el.getAttribute("type") === "date"
    )
    expect(dateTypeInputs.length).toBe(2)
  })

  it("shows DataTable when loaded", () => {
    mockUseNotifications.mockReturnValue({ data: [], isLoading: false })
    renderWithQuery(<NotificationTable />)
    expect(screen.getByTestId("data-table")).toBeDefined()
  })
})
