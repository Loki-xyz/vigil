"use client"

import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  type SortingState,
  type FilterFn,
} from "@tanstack/react-table"
import { Plus, Search } from "lucide-react"
import { Header } from "@/components/layout/header"
import { DataTable } from "@/components/ui/data-table"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { watchColumns } from "@/components/watches/watch-columns"
import { WatchForm } from "@/components/watches/watch-form"
import { useWatches, useCreateWatch } from "@/lib/hooks/use-watches"
import { Skeleton } from "@/components/ui/skeleton"
import { toast } from "sonner"
import type { Watch } from "@/lib/supabase/types"
import type { WatchFormValues } from "@/lib/validations/watch"

const watchFilterFn: FilterFn<Watch> = (row, _columnId, filterValue) => {
  const { search, type, status } = filterValue as {
    search?: string
    type?: string
    status?: string
  }

  if (type && row.original.watch_type !== type) return false
  if (status !== undefined) {
    const isActive = status === "active"
    if (row.original.is_active !== isActive) return false
  }
  if (search) {
    const q = search.toLowerCase()
    const name = (row.original.name ?? "").toLowerCase()
    const terms = (row.original.query_terms ?? "").toLowerCase()
    if (!name.includes(q) && !terms.includes(q)) return false
  }

  return true
}

export function WatchesContent() {
  const searchParams = useSearchParams()
  const [dialogOpen, setDialogOpen] = useState(false)

  useEffect(() => {
    if (searchParams.get("new") === "true") {
      setDialogOpen(true)
    }
  }, [searchParams])
  const [sorting, setSorting] = useState<SortingState>([])
  const [searchQuery, setSearchQuery] = useState("")
  const [typeFilter, setTypeFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const { data: watches, isLoading } = useWatches()
  const createWatch = useCreateWatch()

  const globalFilter = useMemo(
    () => ({
      search: searchQuery || undefined,
      type: typeFilter || undefined,
      status: statusFilter || undefined,
    }),
    [searchQuery, typeFilter, statusFilter]
  )

  const table = useReactTable({
    data: watches ?? [],
    columns: watchColumns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    globalFilterFn: watchFilterFn,
    onSortingChange: setSorting,
    state: { sorting, globalFilter },
  })

  const handleCreate = async (values: WatchFormValues) => {
    await createWatch.mutateAsync(values)
    toast.success("Watch created successfully")
    setDialogOpen(false)
  }

  return (
    <div className="space-y-6">
      <Header
        title="Watches"
        description="Monitor entities, topics, and statutory references"
        actions={
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" />
            New Watch
          </Button>
        }
      />

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search watches..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v.trim())}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All Types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value=" ">All Types</SelectItem>
            <SelectItem value="entity">Entity</SelectItem>
            <SelectItem value="topic">Topic</SelectItem>
            <SelectItem value="act">Act</SelectItem>
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v.trim())}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All Statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value=" ">All Statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="paused">Paused</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <div className="rounded-md border">
          <div className="border-b px-4 py-3 flex items-center gap-4">
            <Skeleton className="h-4 w-[140px]" />
            <Skeleton className="h-4 w-[70px]" />
            <Skeleton className="h-4 w-[60px]" />
            <Skeleton className="h-4 w-[90px]" />
            <Skeleton className="h-4 w-[70px]" />
            <Skeleton className="h-4 w-8 ml-auto" />
          </div>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="border-b last:border-0 px-4 py-3 flex items-center gap-4">
              <Skeleton className="h-4 w-[160px]" />
              <Skeleton className="h-5 w-[60px] rounded-full" />
              <Skeleton className="h-5 w-[56px] rounded-full" />
              <Skeleton className="h-4 w-[80px]" />
              <Skeleton className="h-4 w-[40px]" />
              <Skeleton className="h-6 w-6 ml-auto rounded" />
            </div>
          ))}
        </div>
      ) : (
        <DataTable table={table} />
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Watch</DialogTitle>
            <DialogDescription>
              Set up monitoring for an entity, topic, or statutory reference.
            </DialogDescription>
          </DialogHeader>
          <WatchForm
            onSubmit={handleCreate}
            isSubmitting={createWatch.isPending}
          />
        </DialogContent>
      </Dialog>
    </div>
  )
}
