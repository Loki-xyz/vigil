import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import * as nextThemes from "next-themes"
import { ThemeToggle } from "@/components/layout/theme-toggle"

describe("ThemeToggle", () => {
  it("renders toggle button with sr-only text", () => {
    render(<ThemeToggle />)
    expect(screen.getByText("Toggle theme")).toBeDefined()
  })

  it("calls setTheme('light') when current theme is dark", async () => {
    const setTheme = vi.fn()
    vi.mocked(nextThemes.useTheme).mockReturnValue({
      theme: "dark",
      setTheme,
      themes: ["light", "dark"],
      resolvedTheme: "dark",
      systemTheme: "light",
      forcedTheme: undefined,
    })

    render(<ThemeToggle />)
    const button = screen.getByRole("button")
    await userEvent.click(button)
    expect(setTheme).toHaveBeenCalledWith("light")
  })

  it("calls setTheme('dark') when current theme is light", async () => {
    const setTheme = vi.fn()
    vi.mocked(nextThemes.useTheme).mockReturnValue({
      theme: "light",
      setTheme,
      themes: ["light", "dark"],
      resolvedTheme: "light",
      systemTheme: "light",
      forcedTheme: undefined,
    })

    render(<ThemeToggle />)
    const button = screen.getByRole("button")
    await userEvent.click(button)
    expect(setTheme).toHaveBeenCalledWith("dark")
  })
})
