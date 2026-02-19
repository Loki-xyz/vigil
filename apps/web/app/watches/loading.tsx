import { Skeleton } from "@/components/ui/skeleton"

export default function WatchesLoading() {
  return (
    <div className="space-y-6">
      {/* Header + New Watch button */}
      <div className="flex items-center justify-between">
        <div>
          <Skeleton className="h-8 w-36" />
          <Skeleton className="mt-1 h-4 w-72" />
        </div>
        <Skeleton className="h-9 w-28" />
      </div>

      {/* Table */}
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
    </div>
  )
}
