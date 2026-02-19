import { describe, it, expect, vi, afterEach } from "vitest"
import { cn, formatIST, formatRelativeTime } from "@/lib/utils"

describe("cn", () => {
  it("merges classes", () => {
    expect(cn("px-2", "py-3")).toBe("px-2 py-3")
  })

  it("resolves tailwind conflicts", () => {
    expect(cn("px-2", "px-4")).toBe("px-4")
  })

  it("handles conditionals", () => {
    expect(cn("base", false && "hidden")).toBe("base")
  })
})

describe("formatIST", () => {
  it("converts UTC to IST", () => {
    const result = formatIST("2026-02-17T00:00:00Z")
    expect(result).toContain("17 Feb 2026")
    expect(result).toContain("05:30")
  })

  it("accepts custom format", () => {
    const result = formatIST("2026-02-17T10:00:00Z", "yyyy-MM-dd")
    expect(result).toBe("2026-02-17")
  })

  it("accepts Date object", () => {
    const result = formatIST(new Date("2026-02-17T12:00:00Z"))
    expect(result).toContain("17 Feb 2026")
    expect(result).toContain("17:30")
  })
})

describe("formatRelativeTime", () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns "just now" for < 60 seconds ago', () => {
    vi.useFakeTimers()
    const now = new Date("2026-02-17T12:00:00Z")
    vi.setSystemTime(now)
    const thirtySecondsAgo = new Date("2026-02-17T11:59:30Z")
    expect(formatRelativeTime(thirtySecondsAgo)).toBe("just now")
  })

  it("returns minutes ago", () => {
    vi.useFakeTimers()
    const now = new Date("2026-02-17T12:00:00Z")
    vi.setSystemTime(now)

    const fiveMinAgo = new Date("2026-02-17T11:55:00Z")
    expect(formatRelativeTime(fiveMinAgo)).toBe("5 minutes ago")

    const oneMinAgo = new Date("2026-02-17T11:59:00Z")
    expect(formatRelativeTime(oneMinAgo)).toBe("1 minute ago")
  })

  it("returns hours ago", () => {
    vi.useFakeTimers()
    const now = new Date("2026-02-17T12:00:00Z")
    vi.setSystemTime(now)

    const threeHoursAgo = new Date("2026-02-17T09:00:00Z")
    expect(formatRelativeTime(threeHoursAgo)).toBe("3 hours ago")

    const oneHourAgo = new Date("2026-02-17T11:00:00Z")
    expect(formatRelativeTime(oneHourAgo)).toBe("1 hour ago")
  })

  it("returns days ago", () => {
    vi.useFakeTimers()
    const now = new Date("2026-02-17T12:00:00Z")
    vi.setSystemTime(now)

    const twoDaysAgo = new Date("2026-02-15T12:00:00Z")
    expect(formatRelativeTime(twoDaysAgo)).toBe("2 days ago")

    const oneDayAgo = new Date("2026-02-16T12:00:00Z")
    expect(formatRelativeTime(oneDayAgo)).toBe("1 day ago")
  })
})
