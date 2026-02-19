import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { CourtBadge } from "@/components/judgments/court-badge"

describe("CourtBadge", () => {
  it("renders Supreme Court with purple classes", () => {
    const { container } = render(<CourtBadge court="Supreme Court of India" />)
    const badge = screen.getByText("Supreme Court of India")
    expect(badge.className).toMatch(/purple/)
  })

  it("renders Delhi High Court with blue classes", () => {
    render(<CourtBadge court="Delhi High Court" />)
    const badge = screen.getByText("Delhi High Court")
    expect(badge.className).toMatch(/blue/)
  })

  it("renders Bombay High Court with red classes", () => {
    render(<CourtBadge court="Bombay High Court" />)
    const badge = screen.getByText("Bombay High Court")
    expect(badge.className).toMatch(/red/)
  })

  it("renders unknown court with muted fallback classes", () => {
    render(<CourtBadge court="Gujarat High Court" />)
    const badge = screen.getByText("Gujarat High Court")
    expect(badge.className).toMatch(/bg-muted/)
  })

  it("renders nothing when court is null", () => {
    const { container } = render(<CourtBadge court={null} />)
    expect(container.firstChild).toBeNull()
  })

  it("renders badge with outline variant", () => {
    render(<CourtBadge court="Supreme Court of India" />)
    const badge = screen.getByText("Supreme Court of India")
    expect(badge.className).toMatch(/border/)
  })
})
