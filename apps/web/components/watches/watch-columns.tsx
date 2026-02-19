"use client"

import { useState } from "react"
import Link from "next/link"
import { type ColumnDef } from "@tanstack/react-table"
import { MoreHorizontal, Pencil, Pause, Play, RefreshCw, Trash2 } from "lucide-react"
import type { Watch } from "@/lib/supabase/types"
import { WatchTypeBadge, StatusBadge } from "@/components/watches/watch-type-badge"
import { PollNowButton } from "@/components/watches/poll-now-button"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { formatRelativeTime } from "@/lib/utils"
import { useUpdateWatch, useDeleteWatch } from "@/lib/hooks/use-watches"
import { toast } from "sonner"

export const watchColumns: ColumnDef<Watch>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <Link
        href={`/watches/${row.original.id}`}
        className="font-medium hover:underline"
      >
        {row.original.name}
      </Link>
    ),
  },
  {
    accessorKey: "watch_type",
    header: "Type",
    cell: ({ row }) => <WatchTypeBadge type={row.original.watch_type} />,
  },
  {
    accessorKey: "is_active",
    header: "Status",
    cell: ({ row }) => <StatusBadge isActive={row.original.is_active} />,
  },
  {
    accessorKey: "last_polled_at",
    header: "Last Polled",
    cell: ({ row }) =>
      row.original.last_polled_at
        ? formatRelativeTime(row.original.last_polled_at)
        : "Never",
  },
  {
    accessorKey: "last_poll_result_count",
    header: "Matches",
  },
  {
    id: "actions",
    cell: ({ row }) => <WatchRowActions watch={row.original} />,
  },
]

function WatchRowActions({ watch }: { watch: Watch }) {
  const [deleteOpen, setDeleteOpen] = useState(false)
  const updateWatch = useUpdateWatch()
  const deleteWatch = useDeleteWatch()

  const toggleActive = () => {
    updateWatch.mutate(
      { id: watch.id, is_active: !watch.is_active },
      {
        onSuccess: () => {
          toast.success(
            watch.is_active ? "Watch paused" : "Watch resumed"
          )
        },
      }
    )
  }

  const handleDelete = () => {
    deleteWatch.mutate(watch.id, {
      onSuccess: () => {
        toast.success("Watch deleted")
        setDeleteOpen(false)
      },
    })
  }

  return (
    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
      <PollNowButton watchId={watch.id} />
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-xs">
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem asChild>
            <Link href={`/watches/${watch.id}`}>
              <Pencil />
              Edit
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem onClick={toggleActive}>
            {watch.is_active ? <Pause /> : <Play />}
            {watch.is_active ? "Pause" : "Resume"}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            variant="destructive"
            onClick={() => setDeleteOpen(true)}
          >
            <Trash2 />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Watch</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &ldquo;{watch.name}&rdquo;? This
              will remove the watch and all its matches. This action cannot be
              undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteWatch.isPending}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
