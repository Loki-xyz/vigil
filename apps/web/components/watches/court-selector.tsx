"use client"

import { useState } from "react"
import { Check, ChevronsUpDown } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { COURT_OPTIONS } from "@/lib/constants"

interface CourtSelectorProps {
  value: string[]
  onChange: (value: string[]) => void
}

export function CourtSelector({ value, onChange }: CourtSelectorProps) {
  const [open, setOpen] = useState(false)

  const toggle = (courtValue: string) => {
    if (value.includes(courtValue)) {
      onChange(value.filter((v) => v !== courtValue))
    } else {
      onChange([...value, courtValue])
    }
  }

  const selectedLabels = COURT_OPTIONS.filter((c) => value.includes(c.value))

  return (
    <div className="space-y-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between"
          >
            {value.length === 0
              ? "All Courts"
              : `${value.length} court${value.length === 1 ? "" : "s"} selected`}
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
          <Command>
            <CommandInput placeholder="Search courts..." />
            <CommandList>
              <CommandEmpty>No court found.</CommandEmpty>
              <CommandGroup>
                {COURT_OPTIONS.map((court) => (
                  <CommandItem
                    key={court.value}
                    value={court.label}
                    onSelect={() => toggle(court.value)}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-4 w-4",
                        value.includes(court.value)
                          ? "opacity-100"
                          : "opacity-0"
                      )}
                    />
                    {court.label}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {selectedLabels.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {selectedLabels.map((court) => (
            <Badge
              key={court.value}
              variant="secondary"
              className="cursor-pointer text-xs"
              onClick={() => toggle(court.value)}
            >
              {court.label} &times;
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}
