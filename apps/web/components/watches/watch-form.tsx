"use client"

import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { watchSchema, type WatchFormValues, QUERY_PLACEHOLDERS } from "@/lib/validations/watch"
import { POLLING_INTERVAL_OPTIONS } from "@/lib/constants"
import { CourtSelector } from "@/components/watches/court-selector"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { Loader2 } from "lucide-react"

interface WatchFormProps {
  defaultValues?: Partial<WatchFormValues>
  onSubmit: (values: WatchFormValues) => Promise<void>
  isSubmitting?: boolean
}

export function WatchForm({ defaultValues, onSubmit, isSubmitting }: WatchFormProps) {
  const form = useForm<WatchFormValues>({
    resolver: zodResolver(watchSchema),
    defaultValues: {
      name: "",
      watch_type: "entity",
      query_terms: "",
      court_filter: [],
      polling_interval_minutes: 120,
      ...defaultValues,
    },
  })

  const watchType = form.watch("watch_type")

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Name</FormLabel>
              <FormControl>
                <Input placeholder="e.g., AWS Judgments" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="watch_type"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Watch Type</FormLabel>
              <FormControl>
                <div className="flex gap-2">
                  {(["entity", "topic", "act"] as const).map((type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => field.onChange(type)}
                      className={cn(
                        "flex-1 rounded-md border px-3 py-2 text-sm font-medium capitalize transition-colors",
                        field.value === type
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-input text-muted-foreground hover:bg-accent"
                      )}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="query_terms"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Query Terms</FormLabel>
              <FormControl>
                <Textarea
                  placeholder={QUERY_PLACEHOLDERS[watchType]}
                  className="resize-none"
                  rows={2}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="court_filter"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Court Filter</FormLabel>
              <FormControl>
                <CourtSelector
                  value={field.value}
                  onChange={field.onChange}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="polling_interval_minutes"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Polling Interval</FormLabel>
              <Select
                onValueChange={(v) => field.onChange(Number(v))}
                value={String(field.value)}
              >
                <FormControl>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {POLLING_INTERVAL_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={String(opt.value)}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {defaultValues?.name ? "Save Changes" : "Create Watch"}
        </Button>
      </form>
    </Form>
  )
}
