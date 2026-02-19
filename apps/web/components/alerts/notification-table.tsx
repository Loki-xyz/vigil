"use client"

import { useState } from "react"
import {
  useReactTable,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table"
import { DataTable } from "@/components/ui/data-table"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  useNotifications,
  type NotificationWithWatch,
  type NotificationFilters,
} from "@/lib/hooks/use-notifications"
import {
  NOTIFICATION_STATUS_STYLES,
  NOTIFICATION_CHANNEL_STYLES,
} from "@/lib/constants"
import { formatIST } from "@/lib/utils"
import { cn } from "@/lib/utils"
import type { NotificationChannel, NotificationStatus } from "@/lib/supabase/types"

const columns: ColumnDef<NotificationWithWatch>[] = [
  {
    accessorKey: "created_at",
    header: "Date",
    cell: ({ row }) => formatIST(row.original.created_at),
  },
  {
    id: "watch_name",
    header: "Watch",
    cell: ({ row }) =>
      row.original.watch_matches?.watches?.name ?? "—",
  },
  {
    accessorKey: "channel",
    header: "Channel",
    cell: ({ row }) => (
      <Badge
        variant="outline"
        className={cn(
          "text-xs capitalize",
          NOTIFICATION_CHANNEL_STYLES[row.original.channel]
        )}
      >
        {row.original.channel}
      </Badge>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <Badge
        variant="outline"
        className={cn(
          "text-xs capitalize",
          NOTIFICATION_STATUS_STYLES[row.original.status]
        )}
      >
        {row.original.status}
      </Badge>
    ),
  },
  {
    accessorKey: "recipient",
    header: "Recipient",
    cell: ({ row }) => (
      <span className="text-xs truncate max-w-[200px] block">
        {row.original.recipient}
      </span>
    ),
  },
]

export function NotificationTable() {
  const [sorting, setSorting] = useState<SortingState>([])
  const [channelFilter, setChannelFilter] = useState<string>("")
  const [statusFilter, setStatusFilter] = useState<string>("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")

  const filters: NotificationFilters = {
    channel: (channelFilter || undefined) as NotificationChannel | undefined,
    status: (statusFilter || undefined) as NotificationStatus | undefined,
    dateFrom: dateFrom || undefined,
    dateTo: dateTo || undefined,
  }

  const { data: notifications, isLoading } = useNotifications(filters)

  const table = useReactTable({
    data: notifications ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <Select value={channelFilter} onValueChange={setChannelFilter}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="All Channels" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value=" ">All Channels</SelectItem>
            <SelectItem value="email">Email</SelectItem>
            <SelectItem value="slack">Slack</SelectItem>
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="All Statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value=" ">All Statuses</SelectItem>
            <SelectItem value="sent">Sent</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="retrying">Retrying</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
          </SelectContent>
        </Select>
        <Input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          className="w-[160px]"
        />
        <Input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          className="w-[160px]"
        />
      </div>

      {isLoading ? (
        <div className="rounded-md border">
          <div className="border-b px-4 py-3 flex items-center gap-4">
            <Skeleton className="h-4 w-[60px]" />
            <Skeleton className="h-4 w-[80px]" />
            <Skeleton className="h-4 w-[70px]" />
            <Skeleton className="h-4 w-[60px]" />
            <Skeleton className="h-4 w-[90px]" />
          </div>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="border-b last:border-0 px-4 py-3 flex items-center gap-4">
              <Skeleton className="h-4 w-[100px]" />
              <Skeleton className="h-4 w-[120px]" />
              <Skeleton className="h-5 w-[56px] rounded-full" />
              <Skeleton className="h-5 w-[48px] rounded-full" />
              <Skeleton className="h-4 w-[140px]" />
            </div>
          ))}
        </div>
      ) : (
        <DataTable table={table} />
      )}
    </div>
  )
}
