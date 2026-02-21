import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

const mockUseJudgments = vi.fn()

vi.mock("@/lib/hooks/use-judgments", () => ({
  useJudgments: (filters?: any) => mockUseJudgments(filters),
}))

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

import { JudgmentTable } from "@/components/judgments/judgment-table"

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

describe("JudgmentTable", () => {
  beforeEach(() => {
    mockUseJudgments.mockReturnValue({ data: [], isLoading: false })
  })

  it("shows loading skeletons when isLoading is true", () => {
    mockUseJudgments.mockReturnValue({ data: undefined, isLoading: true })
    const { container } = renderWithQuery(<JudgmentTable />)
    const skeletons = container.querySelectorAll("[data-slot='skeleton']")
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it("renders filter inputs", () => {
    renderWithQuery(<JudgmentTable />)
    expect(screen.getByPlaceholderText("Search judgments...")).toBeDefined()
    // Court select trigger
    expect(screen.getByText("All Courts")).toBeDefined()
    // Two date inputs
    const dateInputs = screen.getAllByDisplayValue("")
    const dateTypeInputs = dateInputs.filter(
      (el) => el.getAttribute("type") === "date"
    )
    expect(dateTypeInputs.length).toBe(2)
  })

  it("shows 'No judgments found.' when data is empty array", () => {
    mockUseJudgments.mockReturnValue({ data: [], isLoading: false })
    renderWithQuery(<JudgmentTable />)
    expect(screen.getByText("No judgments found.")).toBeDefined()
  })

  it("renders table rows when data provided", () => {
    mockUseJudgments.mockReturnValue({
      data: [
        {
          id: "j1",
          ik_doc_id: 12345,
          title: "Test Judgment",
          court: "Supreme Court",
          judgment_date: "2026-02-15",
          headline: "test snippet",
          ik_url: "https://indiankanoon.org/doc/12345/",
          external_url: null,
          source: "ik_api",
          sc_case_number: null,
          num_cites: 5,
          watch_matches: [{ count: 2 }],
        },
      ],
      isLoading: false,
    })
    renderWithQuery(<JudgmentTable />)
    expect(screen.getByText("Test Judgment")).toBeDefined()
  })
})
