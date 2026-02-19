"use client"

import { useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import {
  useReactTable,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  type SortingState,
} from "@tanstack/react-table"
import { Plus } from "lucide-react"
import { Header } from "@/components/layout/header"
import { DataTable } from "@/components/ui/data-table"
import { Button } from "@/components/ui/button"
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
import type { WatchFormValues } from "@/lib/validations/watch"

export function WatchesContent() {
  const searchParams = useSearchParams()
  const [dialogOpen, setDialogOpen] = useState(false)

  useEffect(() => {
    if (searchParams.get("new") === "true") {
      setDialogOpen(true)
    }
  }, [searchParams])
  const [sorting, setSorting] = useState<SortingState>([])
  const { data: watches, isLoading } = useWatches()
  const createWatch = useCreateWatch()

  const table = useReactTable({
    data: watches ?? [],
    columns: watchColumns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
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
