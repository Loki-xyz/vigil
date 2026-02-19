import { Header } from "@/components/layout/header"
import { NotificationTable } from "@/components/alerts/notification-table"

export const dynamic = "force-dynamic"

export default function AlertsPage() {
  return (
    <div className="space-y-6">
      <Header
        title="Alerts"
        description="Notification history and delivery status"
      />
      <NotificationTable />
    </div>
  )
}
