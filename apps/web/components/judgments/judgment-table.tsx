"use client"

import { useState, useMemo } from "react"
import {
  useReactTable,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  getExpandedRowModel,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table"
import { ChevronDown, ChevronRight, ExternalLink, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { CourtBadge } from "@/components/judgments/court-badge"
import { Badge } from "@/components/ui/badge"
import { useJudgments, type JudgmentWithMatchCount } from "@/lib/hooks/use-judgments"
import { COURT_OPTIONS } from "@/lib/constants"
import { formatIST } from "@/lib/utils"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { flexRender } from "@tanstack/react-table"

const columns: ColumnDef<JudgmentWithMatchCount>[] = [
  {
    id: "expand",
    cell: ({ row }) =>
      row.getCanExpand() ? (
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={(e) => {
            e.stopPropagation()
            row.toggleExpanded()
          }}
        >
          {row.getIsExpanded() ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronRight className="h-3 w-3" />
          )}
        </Button>
      ) : null,
  },
  {
    accessorKey: "title",
    header: "Title",
    cell: ({ row }) => (
      <a
        href={row.original.ik_url}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium hover:underline"
        onClick={(e) => e.stopPropagation()}
      >
        {row.original.title}
        <ExternalLink className="inline ml-1 h-3 w-3 text-muted-foreground" />
      </a>
    ),
  },
  {
    accessorKey: "court",
    header: "Court",
    cell: ({ row }) => <CourtBadge court={row.original.court} />,
  },
  {
    accessorKey: "judgment_date",
    header: "Date",
    cell: ({ row }) =>
      row.original.judgment_date
        ? formatIST(row.original.judgment_date, "dd MMM yyyy")
        : "—",
  },
  {
    id: "match_count",
    header: "Watches",
    cell: ({ row }) => {
      const count = row.original.watch_matches?.[0]?.count ?? 0
      return (
        <Badge variant="secondary" className="text-xs">
          {count}
        </Badge>
      )
    },
  },
  {
    accessorKey: "num_cites",
    header: "Citations",
  },
]

export function JudgmentTable() {
  const [sorting, setSorting] = useState<SortingState>([])
  const [courtFilter, setCourtFilter] = useState<string>("")
  const [searchQuery, setSearchQuery] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")

  const filters = useMemo(
    () => ({
      court: courtFilter || undefined,
      search: searchQuery || undefined,
      dateFrom: dateFrom || undefined,
      dateTo: dateTo || undefined,
    }),
    [courtFilter, searchQuery, dateFrom, dateTo]
  )

  const { data: judgments, isLoading } = useJudgments(filters)

  const table = useReactTable({
    data: judgments ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
    getRowCanExpand: (row) => !!row.original.headline,
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search judgments..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={courtFilter} onValueChange={setCourtFilter}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="All Courts" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value=" ">All Courts</SelectItem>
            {COURT_OPTIONS.map((c) => (
              <SelectItem key={c.value} value={c.label}>
                {c.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          className="w-[160px]"
          placeholder="From"
        />
        <Input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          className="w-[160px]"
          placeholder="To"
        />
      </div>

      {isLoading ? (
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
      ) : (
        <div className="space-y-4">
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                {table.getHeaderGroups().map((headerGroup) => (
                  <TableRow key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <TableHead key={header.id}>
                        {header.isPlaceholder
                          ? null
                          : flexRender(
                              header.column.columnDef.header,
                              header.getContext()
                            )}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {table.getRowModel().rows.length ? (
                  table.getRowModel().rows.map((row) => (
                    <>
                      <TableRow
                        key={row.id}
                        className="cursor-pointer"
                        onClick={() => row.toggleExpanded()}
                      >
                        {row.getVisibleCells().map((cell) => (
                          <TableCell key={cell.id}>
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext()
                            )}
                          </TableCell>
                        ))}
                      </TableRow>
                      {row.getIsExpanded() && (
                        <TableRow key={`${row.id}-expanded`}>
                          <TableCell
                            colSpan={columns.length}
                            className="bg-muted/30 text-sm text-muted-foreground"
                          >
                            <div className="px-4 py-3">
                              <p className="font-medium text-foreground mb-1">
                                Headline
                              </p>
                              <p
                                dangerouslySetInnerHTML={{
                                  __html:
                                    row.original.headline ?? "No headline available.",
                                }}
                              />
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </>
                  ))
                ) : (
                  <TableRow>
                    <TableCell
                      colSpan={columns.length}
                      className="h-24 text-center text-muted-foreground"
                    >
                      No judgments found.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      )}
    </div>
  )
}
