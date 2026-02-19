import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"

vi.mock("@/components/watches/court-selector", () => ({
  CourtSelector: ({ value, onChange }: any) => <div data-testid="court-selector" />,
}))

import { WatchForm } from "@/components/watches/watch-form"

describe("WatchForm", () => {
  const defaultOnSubmit = vi.fn().mockResolvedValue(undefined)

  it("renders name input field", () => {
    render(<WatchForm onSubmit={defaultOnSubmit} />)
    expect(screen.getByText("Name")).toBeDefined()
    expect(screen.getByPlaceholderText("e.g., AWS Judgments")).toBeDefined()
  })

  it("renders 3 watch type buttons (entity, topic, act)", () => {
    render(<WatchForm onSubmit={defaultOnSubmit} />)
    expect(screen.getByText("entity")).toBeDefined()
    expect(screen.getByText("topic")).toBeDefined()
    expect(screen.getByText("act")).toBeDefined()
  })

  it("renders query terms textarea", () => {
    render(<WatchForm onSubmit={defaultOnSubmit} />)
    expect(screen.getByText("Query Terms")).toBeDefined()
  })

  it("shows 'Create Watch' button when no defaultValues.name", () => {
    render(<WatchForm onSubmit={defaultOnSubmit} />)
    expect(screen.getByText("Create Watch")).toBeDefined()
  })

  it("shows 'Save Changes' button when defaultValues.name provided", () => {
    render(
      <WatchForm
        onSubmit={defaultOnSubmit}
        defaultValues={{
          name: "Existing Watch",
          watch_type: "entity",
          query_terms: "test",
          court_filter: [],
          polling_interval_minutes: 120,
        }}
      />
    )
    expect(screen.getByText("Save Changes")).toBeDefined()
  })
})
