"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  LayoutDashboard,
  Eye,
  Scale,
  Bell,
  Settings,
  Plus,
} from "lucide-react"
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "@/components/ui/command"
import { useWatches } from "@/lib/hooks/use-watches"
import { WatchTypeBadge } from "@/components/watches/watch-type-badge"

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/watches", label: "Watches", icon: Eye },
  { href: "/judgments", label: "Judgments", icon: Scale },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/settings", label: "Settings", icon: Settings },
]

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const router = useRouter()
  const { data: watches } = useWatches()

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
    }
    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [])

  function navigate(href: string) {
    setOpen(false)
    router.push(href)
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen} showCloseButton={false}>
      <CommandInput placeholder="Search pages, watches, actions..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigation">
          {navItems.map((item) => (
            <CommandItem
              key={item.href}
              value={item.label}
              onSelect={() => navigate(item.href)}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </CommandItem>
          ))}
        </CommandGroup>
        {watches && watches.length > 0 && (
          <CommandGroup heading="Watches">
            {watches.map((watch) => (
              <CommandItem
                key={watch.id}
                value={`${watch.name} ${watch.watch_type}`}
                onSelect={() => navigate(`/watches/${watch.id}`)}
              >
                <Eye className="h-4 w-4" />
                <span className="flex-1">{watch.name}</span>
                <WatchTypeBadge type={watch.watch_type} />
              </CommandItem>
            ))}
          </CommandGroup>
        )}
        <CommandGroup heading="Actions">
          <CommandItem
            value="Create New Watch"
            onSelect={() => navigate("/watches?new=true")}
          >
            <Plus className="h-4 w-4" />
            Create New Watch
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
