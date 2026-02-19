import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

// Color-coded badge per court
const courtColors: Record<string, string> = {
  "Supreme Court of India": "bg-purple-500/20 text-purple-400 border-purple-500/30",
  "Delhi High Court": "bg-blue-500/20 text-blue-400 border-blue-500/30",
  "Bombay High Court": "bg-red-500/20 text-red-400 border-red-500/30",
  "Madras High Court": "bg-green-500/20 text-green-400 border-green-500/30",
  "Kolkata High Court": "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  "Karnataka High Court": "bg-orange-500/20 text-orange-400 border-orange-500/30",
  "Andhra Pradesh High Court": "bg-teal-500/20 text-teal-400 border-teal-500/30",
  "Madhya Pradesh High Court": "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
}

export function CourtBadge({ court }: { court: string | null }) {
  if (!court) return null

  const colorClass = courtColors[court] ?? "bg-muted text-muted-foreground"

  return (
    <Badge variant="outline" className={cn("text-xs", colorClass)}>
      {court}
    </Badge>
  )
}
