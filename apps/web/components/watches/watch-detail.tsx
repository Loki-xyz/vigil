"use client"

import { useState } from "react"
import Link from "next/link"
import {
  useReactTable,
  getCoreRowModel,
  getPaginationRowModel,
  type ColumnDef,
} from "@tanstack/react-table"
import { ArrowLeft, Pencil } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { COURT_OPTIONS } from "@/lib/constants"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DataTable } from "@/components/ui/data-table"
import { WatchTypeBadge, StatusBadge } from "@/components/watches/watch-type-badge"
import { CourtBadge } from "@/components/judgments/court-badge"
import { PollNowButton } from "@/components/watches/poll-now-button"
import { WatchForm } from "@/components/watches/watch-form"
import {
  useWatch,
  useUpdateWatch,
  useWatchMatches,
  useWatchApiLog,
} from "@/lib/hooks/use-watches"
import { formatIST, formatRelativeTime } from "@/lib/utils"
import { toast } from "sonner"
import type { WatchMatch, ApiCallLogEntry } from "@/lib/supabase/types"
import type { WatchFormValues } from "@/lib/validations/watch"

const matchColumns: ColumnDef<WatchMatch>[] = [
  {
    accessorKey: "judgments.title",
    header: "Title",
    cell: ({ row }) => {
      const j = row.original.judgments
      return j ? (
        <a
          href={j.ik_url}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium hover:underline"
        >
          {j.title}
        </a>
      ) : (
        "—"
      )
    },
  },
  {
    accessorKey: "judgments.court",
    header: "Court",
    cell: ({ row }) => (
      <CourtBadge court={row.original.judgments?.court ?? null} />
    ),
  },
  {
    accessorKey: "judgments.judgment_date",
    header: "Date",
    cell: ({ row }) =>
      row.original.judgments?.judgment_date
        ? formatIST(row.original.judgments.judgment_date, "dd MMM yyyy")
        : "—",
  },
  {
    accessorKey: "snippet",
    header: "Snippet",
    cell: ({ row }) => (
      <span className="text-xs text-muted-foreground line-clamp-1">
        {row.original.snippet ?? "—"}
      </span>
    ),
  },
  {
    accessorKey: "matched_at",
    header: "Matched",
    cell: ({ row }) => formatRelativeTime(row.original.matched_at),
  },
]

const apiLogColumns: ColumnDef<ApiCallLogEntry>[] = [
  {
    accessorKey: "created_at",
    header: "Time",
    cell: ({ row }) => formatIST(row.original.created_at),
  },
  { accessorKey: "endpoint", header: "Endpoint" },
  {
    accessorKey: "http_status",
    header: "Status",
    cell: ({ row }) => {
      const status = row.original.http_status
      return status ? (
        <Badge
          variant="outline"
          className={
            status < 400
              ? "bg-green-500/20 text-green-400 border-green-500/30"
              : "bg-red-500/20 text-red-400 border-red-500/30"
          }
        >
          {status}
        </Badge>
      ) : (
        "—"
      )
    },
  },
  { accessorKey: "result_count", header: "Results" },
  {
    accessorKey: "response_time_ms",
    header: "Response Time",
    cell: ({ row }) =>
      row.original.response_time_ms
        ? `${row.original.response_time_ms}ms`
        : "—",
  },
]

export function WatchDetail({ id }: { id: string }) {
  const [editing, setEditing] = useState(false)
  const { data: watch, isLoading } = useWatch(id)
  const { data: matches } = useWatchMatches(id)
  const { data: apiLog } = useWatchApiLog(id)
  const updateWatch = useUpdateWatch()

  const matchTable = useReactTable({
    data: matches ?? [],
    columns: matchColumns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  })

  const apiLogTable = useReactTable({
    data: apiLog ?? [],
    columns: apiLogColumns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-8 w-8 rounded" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-7 w-48" />
            <div className="flex gap-2">
              <Skeleton className="h-5 w-16 rounded-full" />
              <Skeleton className="h-5 w-14 rounded-full" />
            </div>
          </div>
          <Skeleton className="h-8 w-20 rounded" />
          <Skeleton className="h-8 w-16 rounded" />
        </div>
        <Card>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="space-y-1">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-5 w-40" />
              </div>
            ))}
          </CardContent>
        </Card>
        <div className="space-y-4">
          <div className="flex gap-4 border-b">
            <Skeleton className="h-9 w-36" />
            <Skeleton className="h-9 w-28" />
          </div>
          <div className="rounded-md border">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="border-b last:border-0 px-4 py-3 flex items-center gap-4">
                <Skeleton className="h-4 w-[200px]" />
                <Skeleton className="h-5 w-[60px] rounded-full" />
                <Skeleton className="h-4 w-[80px]" />
                <Skeleton className="h-4 w-[120px]" />
                <Skeleton className="h-4 w-[70px]" />
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (!watch) {
    return <p className="text-muted-foreground">Watch not found.</p>
  }

  const handleUpdate = async (values: WatchFormValues) => {
    await updateWatch.mutateAsync({ id: watch.id, ...values })
    toast.success("Watch updated")
    setEditing(false)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon-sm" asChild>
          <Link href="/watches">
            <ArrowLeft />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="font-serif text-2xl font-semibold tracking-tight">
            {watch.name}
          </h1>
          <div className="mt-1 flex items-center gap-2">
            <WatchTypeBadge type={watch.watch_type} />
            <StatusBadge isActive={watch.is_active} />
          </div>
        </div>
        <PollNowButton watchId={watch.id} />
        <Button
          variant="outline"
          size="sm"
          onClick={() => setEditing(!editing)}
        >
          <Pencil className="h-4 w-4" />
          {editing ? "Cancel" : "Edit"}
        </Button>
      </div>

      {editing ? (
        <Card>
          <CardHeader>
            <CardTitle>Edit Watch</CardTitle>
          </CardHeader>
          <CardContent>
            <WatchForm
              defaultValues={{
                name: watch.name,
                watch_type: watch.watch_type,
                query_terms: watch.query_terms,
                court_filter: watch.court_filter,
                polling_interval_minutes: watch.polling_interval_minutes,
              }}
              onSubmit={handleUpdate}
              isSubmitting={updateWatch.isPending}
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <span className="text-muted-foreground">Query Terms</span>
              <p className="font-medium">{watch.query_terms}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Court Filter</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {watch.court_filter.length > 0
                  ? watch.court_filter.map((c) => (
                      <Badge key={c} variant="secondary" className="text-xs">
                        {COURT_OPTIONS.find((opt) => opt.value === c)?.label ?? c}
                      </Badge>
                    ))
                  : "All Courts"}
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Polling Interval</span>
              <p className="font-medium">
                Every {watch.polling_interval_minutes / 60} hours
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Last Polled</span>
              <p className="font-medium">
                {watch.last_polled_at
                  ? formatRelativeTime(watch.last_polled_at)
                  : "Never"}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="matches">
        <TabsList variant="line">
          <TabsTrigger value="matches">
            Matched Judgments ({matches?.length ?? 0})
          </TabsTrigger>
          <TabsTrigger value="history">
            Poll History ({apiLog?.length ?? 0})
          </TabsTrigger>
        </TabsList>
        <TabsContent value="matches">
          <DataTable table={matchTable} />
        </TabsContent>
        <TabsContent value="history">
          <DataTable table={apiLogTable} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
