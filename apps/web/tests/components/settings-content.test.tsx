import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

const mockUseSettings = vi.fn()
const mockUseUpdateSetting = vi.fn()
const mockUseClearMatchData = vi.fn()
const mockUseResetSettings = vi.fn()

vi.mock("@/lib/hooks/use-settings", () => ({
  useSettings: () => mockUseSettings(),
  useUpdateSetting: () => mockUseUpdateSetting(),
  useClearMatchData: () => mockUseClearMatchData(),
  useResetSettings: () => mockUseResetSettings(),
}))

vi.mock("@/components/layout/header", () => ({
  Header: ({ title, description }: { title: string; description?: string }) => (
    <div data-testid="header">
      <h1>{title}</h1>
      {description && <p>{description}</p>}
    </div>
  ),
}))

vi.mock("@/components/watches/court-selector", () => ({
  CourtSelector: ({ value, onChange }: any) => <div data-testid="court-selector" />,
}))

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

import { SettingsContent } from "@/components/settings/settings-content"

const mockSettings = {
  notification_email_enabled: "true",
  notification_slack_enabled: "false",
  notification_email_recipients: "test@example.com",
  notification_slack_webhook_url: "",
  default_court_filter: "",
  global_polling_enabled: "true",
  daily_digest_enabled: "true",
  daily_digest_time: "09:00",
}

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

describe("SettingsContent", () => {
  beforeEach(() => {
    mockUseSettings.mockReturnValue({ data: mockSettings, isLoading: false })
    mockUseUpdateSetting.mockReturnValue({ mutate: vi.fn(), isPending: false })
    mockUseClearMatchData.mockReturnValue({ mutate: vi.fn(), isPending: false })
    mockUseResetSettings.mockReturnValue({ mutate: vi.fn(), isPending: false })
  })

  it("shows loading skeletons when isLoading is true", () => {
    mockUseSettings.mockReturnValue({ data: undefined, isLoading: true })
    const { container } = renderWithQuery(<SettingsContent />)
    const skeletons = container.querySelectorAll("[data-slot='skeleton']")
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it("renders 'Notifications' card title when loaded", () => {
    renderWithQuery(<SettingsContent />)
    expect(screen.getByText("Notifications")).toBeDefined()
  })

  it("renders 'Polling' card title", () => {
    renderWithQuery(<SettingsContent />)
    expect(screen.getByText("Polling")).toBeDefined()
  })

  it("renders 'Daily Digest' card title", () => {
    renderWithQuery(<SettingsContent />)
    // The card title and the switch label both say "Daily Digest"
    const elements = screen.getAllByText("Daily Digest")
    expect(elements.length).toBeGreaterThanOrEqual(1)
  })

  it("renders 'Danger Zone' card title with 'Clear Data' and 'Reset Settings' buttons", () => {
    renderWithQuery(<SettingsContent />)
    expect(screen.getByText("Danger Zone")).toBeDefined()
    expect(screen.getByText("Clear Data")).toBeDefined()
    expect(screen.getByText("Reset Settings")).toBeDefined()
  })
})
