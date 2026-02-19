import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { Header } from "@/components/layout/header"

describe("Header", () => {
  it("renders title in h1", () => {
    render(<Header title="Dashboard" />)
    const heading = screen.getByRole("heading", { level: 1 })
    expect(heading.textContent).toBe("Dashboard")
  })

  it("renders description when provided", () => {
    render(<Header title="Dashboard" description="Overview of the system" />)
    expect(screen.getByText("Overview of the system")).toBeDefined()
  })

  it("does not render description when omitted", () => {
    const { container } = render(<Header title="Dashboard" />)
    const paragraphs = container.querySelectorAll("p")
    expect(paragraphs.length).toBe(0)
  })

  it("includes theme toggle button", () => {
    render(<Header title="Dashboard" />)
    expect(screen.getByText("Toggle theme")).toBeDefined()
  })
})
