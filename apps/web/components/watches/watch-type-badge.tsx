import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { WATCH_TYPE_STYLES } from "@/lib/constants"
import type { WatchType } from "@/lib/supabase/types"

export function WatchTypeBadge({ type }: { type: WatchType }) {
  return (
    <Badge variant="outline" className={cn("text-xs capitalize", WATCH_TYPE_STYLES[type])}>
      {type}
    </Badge>
  )
}

export function StatusBadge({ isActive }: { isActive: boolean }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-xs",
        isActive
          ? "bg-green-500/20 text-green-400 border-green-500/30"
          : "bg-muted text-muted-foreground"
      )}
    >
      {isActive ? "Active" : "Paused"}
    </Badge>
  )
}
