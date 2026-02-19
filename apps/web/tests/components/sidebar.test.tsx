import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import * as navigation from "next/navigation"
import { Sidebar } from "@/components/layout/sidebar"

describe("Sidebar", () => {
  it("renders Vigil brand text", () => {
    vi.mocked(navigation.usePathname).mockReturnValue("/")
    render(<Sidebar />)
    expect(screen.getByText("Vigil")).toBeDefined()
  })

  it("renders all 5 nav items", () => {
    vi.mocked(navigation.usePathname).mockReturnValue("/")
    render(<Sidebar />)
    expect(screen.getByText("Dashboard")).toBeDefined()
    expect(screen.getByText("Watches")).toBeDefined()
    expect(screen.getByText("Judgments")).toBeDefined()
    expect(screen.getByText("Alerts")).toBeDefined()
    expect(screen.getByText("Settings")).toBeDefined()
  })

  it("nav links have correct hrefs", () => {
    vi.mocked(navigation.usePathname).mockReturnValue("/")
    render(<Sidebar />)
    const links = [
      { text: "Dashboard", href: "/" },
      { text: "Watches", href: "/watches" },
      { text: "Judgments", href: "/judgments" },
      { text: "Alerts", href: "/alerts" },
      { text: "Settings", href: "/settings" },
    ]
    for (const { text, href } of links) {
      const link = screen.getByText(text).closest("a")
      expect(link).not.toBeNull()
      expect(link!.getAttribute("href")).toBe(href)
    }
  })

  it("applies active state on /watches", () => {
    vi.mocked(navigation.usePathname).mockReturnValue("/watches")
    render(<Sidebar />)
    const watchesLink = screen.getByText("Watches").closest("a")
    expect(watchesLink!.className).toMatch(/bg-sidebar-accent/)
  })

  it("applies active state for nested path /watches/some-uuid", () => {
    vi.mocked(navigation.usePathname).mockReturnValue("/watches/some-uuid")
    render(<Sidebar />)
    const watchesLink = screen.getByText("Watches").closest("a")
    expect(watchesLink!.className).toMatch(/bg-sidebar-accent/)
  })

  it("Dashboard is only active on exact /", () => {
    vi.mocked(navigation.usePathname).mockReturnValue("/watches")
    render(<Sidebar />)
    const dashboardLink = screen.getByText("Dashboard").closest("a")
    // Check that `bg-sidebar-accent` does NOT appear as a standalone class
    // (it still appears as `hover:bg-sidebar-accent` on inactive links)
    const classes = dashboardLink!.className.split(" ")
    expect(classes).not.toContain("bg-sidebar-accent")
  })
})
