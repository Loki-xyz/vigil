import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import * as navigation from "next/navigation"

vi.mock("@/lib/supabase/client", () => ({
  supabase: {
    from: vi.fn(() => ({
      select: vi.fn().mockReturnThis(),
      order: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      then: vi.fn(),
    })),
  },
  createClient: vi.fn(),
}))

vi.mock("@/lib/hooks/use-watches", () => ({
  useWatches: vi.fn(() => ({
    data: [
      { id: "w1", name: "AWS Watch", watch_type: "entity" },
      { id: "w2", name: "DPDP Act", watch_type: "act" },
    ],
    isLoading: false,
  })),
}))

import { CommandPalette } from "@/components/layout/command-palette"

const mockPush = vi.fn()

function Wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(navigation.useRouter).mockReturnValue({
    push: mockPush,
    replace: vi.fn(),
    back: vi.fn(),
    prefetch: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  })
})

describe("CommandPalette", () => {
  it("opens on Cmd+K", () => {
    render(<CommandPalette />, { wrapper: Wrapper })

    // Dialog should not be visible initially
    expect(screen.queryByPlaceholderText("Search pages, watches, actions...")).toBeNull()

    // Simulate Cmd+K
    fireEvent.keyDown(document, { key: "k", metaKey: true })

    expect(screen.getByPlaceholderText("Search pages, watches, actions...")).toBeDefined()
  })

  it("renders navigation items when open", () => {
    render(<CommandPalette />, { wrapper: Wrapper })
    fireEvent.keyDown(document, { key: "k", metaKey: true })

    // Use getAllByRole to find command items by their data-value
    const items = screen.getAllByRole("option")
    const itemValues = items.map((el) => el.getAttribute("data-value"))
    expect(itemValues).toContain("Dashboard")
    expect(itemValues).toContain("Watches")
    expect(itemValues).toContain("Judgments")
    expect(itemValues).toContain("Alerts")
    expect(itemValues).toContain("Settings")
  })

  it("renders watches from hook data", () => {
    render(<CommandPalette />, { wrapper: Wrapper })
    fireEvent.keyDown(document, { key: "k", metaKey: true })

    expect(screen.getByText("AWS Watch")).toBeDefined()
    expect(screen.getByText("DPDP Act")).toBeDefined()
  })

  it("renders Create New Watch action", () => {
    render(<CommandPalette />, { wrapper: Wrapper })
    fireEvent.keyDown(document, { key: "k", metaKey: true })

    expect(screen.getByText("Create New Watch")).toBeDefined()
  })

  it("opens with Ctrl+K as well", () => {
    render(<CommandPalette />, { wrapper: Wrapper })
    fireEvent.keyDown(document, { key: "k", ctrlKey: true })

    expect(screen.getByPlaceholderText("Search pages, watches, actions...")).toBeDefined()
  })
})
