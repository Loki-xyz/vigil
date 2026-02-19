import { Skeleton } from "@/components/ui/skeleton"

export default function JudgmentsLoading() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Skeleton className="h-8 w-40" />
        <Skeleton className="mt-1 h-4 w-72" />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <Skeleton className="h-9 flex-1 min-w-[200px]" />
        <Skeleton className="h-9 w-[200px]" />
        <Skeleton className="h-9 w-[160px]" />
        <Skeleton className="h-9 w-[160px]" />
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <div className="border-b px-4 py-3 flex items-center gap-4">
          <Skeleton className="h-4 w-6" />
          <Skeleton className="h-4 w-[140px]" />
          <Skeleton className="h-4 w-[60px]" />
          <Skeleton className="h-4 w-[50px]" />
          <Skeleton className="h-4 w-[70px]" />
          <Skeleton className="h-4 w-[70px]" />
        </div>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="border-b last:border-0 px-4 py-3 flex items-center gap-4">
            <Skeleton className="h-4 w-4 rounded" />
            <Skeleton className="h-4 w-[200px]" />
            <Skeleton className="h-5 w-[70px] rounded-full" />
            <Skeleton className="h-4 w-[80px]" />
            <Skeleton className="h-5 w-8 rounded-full" />
            <Skeleton className="h-4 w-[30px]" />
          </div>
        ))}
      </div>
    </div>
  )
}
