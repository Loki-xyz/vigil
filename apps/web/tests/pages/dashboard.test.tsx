import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"

vi.mock("@/components/layout/header", () => ({
  Header: ({ title, description }: any) => (
    <div data-testid="header">
      {title} - {description}
    </div>
  ),
}))

vi.mock("@/components/dashboard/stats-cards", () => ({
  StatsCards: () => <div data-testid="stats-cards" />,
}))

vi.mock("@/components/dashboard/recent-matches", () => ({
  RecentMatches: () => <div data-testid="recent-matches" />,
}))

vi.mock("@/components/dashboard/court-distribution", () => ({
  CourtDistribution: () => <div data-testid="court-distribution" />,
}))

vi.mock("@/components/dashboard/match-trend-chart", () => ({
  MatchTrendChart: () => <div data-testid="match-trend-chart" />,
}))

vi.mock("@/components/dashboard/top-watches", () => ({
  TopWatches: () => <div data-testid="top-watches" />,
}))

import DashboardPage from "@/app/page"

describe("DashboardPage", () => {
  it("renders header with Dashboard title", () => {
    render(<DashboardPage />)
    const header = screen.getByTestId("header")
    expect(header.textContent).toContain("Dashboard")
    expect(header.textContent).toContain("Judgment monitoring overview")
  })

  it("renders all dashboard sections", () => {
    render(<DashboardPage />)
    expect(screen.getByTestId("stats-cards")).toBeDefined()
    expect(screen.getByTestId("recent-matches")).toBeDefined()
    expect(screen.getByTestId("court-distribution")).toBeDefined()
    expect(screen.getByTestId("match-trend-chart")).toBeDefined()
    expect(screen.getByTestId("top-watches")).toBeDefined()
  })

  it("uses grid layout for rows", () => {
    const { container } = render(<DashboardPage />)
    const gridDivs = container.querySelectorAll("[class*='grid'][class*='lg:grid-cols-3']")
    expect(gridDivs.length).toBe(2)
  })
})
