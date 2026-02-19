"use client"

import { useState } from "react"
import { Header } from "@/components/layout/header"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { CourtSelector } from "@/components/watches/court-selector"
import { Skeleton } from "@/components/ui/skeleton"
import { useSettings, useUpdateSetting, useClearMatchData, useResetSettings } from "@/lib/hooks/use-settings"
import { toast } from "sonner"

export function SettingsContent() {
  const { data: settings, isLoading } = useSettings()
  const updateSetting = useUpdateSetting()
  const clearMatchData = useClearMatchData()
  const resetSettings = useResetSettings()

  const [clearDialogOpen, setClearDialogOpen] = useState(false)
  const [resetDialogOpen, setResetDialogOpen] = useState(false)

  const update = (key: string, value: string) => {
    updateSetting.mutate(
      { key, value },
      { onError: () => toast.error(`Failed to update ${key}`) }
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Header
          title="Settings"
          description="Configure notifications, polling, and system preferences"
        />
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-4 w-64" />
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Skeleton className="h-4 w-36" />
                  <Skeleton className="h-3 w-56" />
                </div>
                <Skeleton className="h-5 w-9 rounded-full" />
              </div>
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-48" />
                </div>
                <Skeleton className="h-5 w-9 rounded-full" />
              </div>
              <div className="space-y-2">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-9 w-full rounded-md" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Header
        title="Settings"
        description="Configure notifications, polling, and system preferences"
      />

      {/* Notifications */}
      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
          <CardDescription>
            Configure how you receive alerts for new matches.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="email-enabled">Email Notifications</Label>
              <p className="text-sm text-muted-foreground">
                Send email alerts when new matches are found
              </p>
            </div>
            <Switch
              id="email-enabled"
              checked={settings?.notification_email_enabled === "true"}
              onCheckedChange={(checked) =>
                update("notification_email_enabled", String(checked))
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="slack-enabled">Slack Notifications</Label>
              <p className="text-sm text-muted-foreground">
                Post alerts to a Slack channel
              </p>
            </div>
            <Switch
              id="slack-enabled"
              checked={settings?.notification_slack_enabled === "true"}
              onCheckedChange={(checked) =>
                update("notification_slack_enabled", String(checked))
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email-recipients">Email Recipients</Label>
            <Input
              id="email-recipients"
              placeholder="email1@example.com, email2@example.com"
              defaultValue={settings?.notification_email_recipients ?? ""}
              onBlur={(e) =>
                update("notification_email_recipients", e.target.value)
              }
            />
            <p className="text-xs text-muted-foreground">
              Comma-separated list of email addresses
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="slack-webhook">Slack Webhook URL</Label>
            <Input
              id="slack-webhook"
              type="url"
              placeholder="https://hooks.slack.com/services/..."
              defaultValue={settings?.slack_webhook_url ?? ""}
              onBlur={(e) => update("slack_webhook_url", e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Polling */}
      <Card>
        <CardHeader>
          <CardTitle>Polling</CardTitle>
          <CardDescription>
            Control the global polling behavior for all watches.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="polling-enabled">Global Polling</Label>
              <p className="text-sm text-muted-foreground">
                Enable or disable all watch polling
              </p>
            </div>
            <Switch
              id="polling-enabled"
              checked={settings?.polling_enabled !== "false"}
              onCheckedChange={(checked) =>
                update("polling_enabled", String(checked))
              }
            />
          </div>
          <div className="space-y-2">
            <Label>Default Court Filter</Label>
            <p className="text-xs text-muted-foreground mb-2">
              Courts to include by default when creating new watches
            </p>
            <CourtSelector
              value={
                settings?.default_court_filter
                  ? settings.default_court_filter.split(",").filter(Boolean)
                  : []
              }
              onChange={(courts) =>
                update("default_court_filter", courts.join(","))
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* Daily Digest */}
      <Card>
        <CardHeader>
          <CardTitle>Daily Digest</CardTitle>
          <CardDescription>
            Receive a summary of all matches from the previous day.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="digest-enabled">Daily Digest</Label>
              <p className="text-sm text-muted-foreground">
                Send a daily summary email
              </p>
            </div>
            <Switch
              id="digest-enabled"
              checked={settings?.daily_digest_enabled === "true"}
              onCheckedChange={(checked) =>
                update("daily_digest_enabled", String(checked))
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="digest-time">Digest Time</Label>
            <Input
              id="digest-time"
              type="time"
              defaultValue={settings?.daily_digest_time ?? "08:00"}
              className="w-[160px]"
              onBlur={(e) => update("daily_digest_time", e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Time to send the daily digest (IST)
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="text-destructive">Danger Zone</CardTitle>
          <CardDescription>
            Irreversible actions. Proceed with caution.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Clear Match Data</p>
              <p className="text-sm text-muted-foreground">
                Delete all matched judgments and watch matches. Watches will be
                preserved.
              </p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setClearDialogOpen(true)}
            >
              Clear Data
            </Button>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Reset All Settings</p>
              <p className="text-sm text-muted-foreground">
                Restore all settings to their default values.
              </p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setResetDialogOpen(true)}
            >
              Reset Settings
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Clear Data Confirmation */}
      <Dialog open={clearDialogOpen} onOpenChange={setClearDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clear Match Data</DialogTitle>
            <DialogDescription>
              This will permanently delete all watch matches and judgments. This
              action cannot be undone. Your watches will be preserved.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setClearDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                clearMatchData.mutate(undefined, {
                  onSuccess: () => {
                    toast.success("Match data cleared")
                    setClearDialogOpen(false)
                  },
                  onError: () => toast.error("Failed to clear data"),
                })
              }}
              disabled={clearMatchData.isPending}
            >
              {clearMatchData.isPending ? "Clearing..." : "Clear All Data"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reset Settings Confirmation */}
      <Dialog open={resetDialogOpen} onOpenChange={setResetDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset All Settings</DialogTitle>
            <DialogDescription>
              This will reset all settings to their default values. This action
              cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setResetDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                resetSettings.mutate(undefined, {
                  onSuccess: () => {
                    toast.success("Settings reset to defaults")
                    setResetDialogOpen(false)
                  },
                  onError: () => toast.error("Failed to reset settings"),
                })
              }}
              disabled={resetSettings.isPending}
            >
              {resetSettings.isPending ? "Resetting..." : "Reset All"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
