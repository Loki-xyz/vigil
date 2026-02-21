"use client"

import { useEffect, useRef, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { supabase } from "@/lib/supabase/client"
import type { PollRequest, PollRequestStatus } from "@/lib/supabase/types"
import { Button } from "@/components/ui/button"
import { Loader2, RefreshCw } from "lucide-react"
import { toast } from "sonner"

const POLL_TIMEOUT_MS = 3 * 60 * 1000 // 3 minutes

export function PollNowButton({ watchId }: { watchId: string }) {
  const [status, setStatus] = useState<PollRequestStatus | null>(null)
  const queryClient = useQueryClient()
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const channelRef = useRef<ReturnType<typeof supabase.channel> | null>(null)

  // Clean up timeout and channel on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      if (channelRef.current) supabase.removeChannel(channelRef.current)
    }
  }, [])

  const cleanup = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    if (channelRef.current) {
      supabase.removeChannel(channelRef.current)
      channelRef.current = null
    }
  }

  const pollMutation = useMutation({
    mutationFn: async () => {
      const { data, error } = await supabase
        .from("poll_requests")
        .insert({ watch_id: watchId, status: "pending" })
        .select()
        .single()
      if (error) throw error
      return data as PollRequest
    },
    onSuccess: (data) => {
      setStatus("pending")
      const channel = supabase
        .channel(`poll_request_${data.id}`)
        .on(
          "postgres_changes",
          {
            event: "UPDATE",
            schema: "public",
            table: "poll_requests",
            filter: `id=eq.${data.id}`,
          },
          (payload) => {
            const newStatus = (payload.new as PollRequest).status
            setStatus(newStatus)
            if (newStatus === "done") {
              toast.success("Poll completed successfully")
              queryClient.invalidateQueries({
                queryKey: ["watches", watchId],
              })
              queryClient.invalidateQueries({
                queryKey: ["dashboard"],
              })
              setStatus(null)
              cleanup()
            } else if (newStatus === "failed") {
              toast.error("Poll failed")
              setStatus(null)
              cleanup()
            }
          }
        )
        .subscribe()

      channelRef.current = channel

      // Client-side timeout: if no response within 3 minutes, reset
      timeoutRef.current = setTimeout(() => {
        toast.error("Poll timed out — the worker may be busy. Try again later.")
        setStatus(null)
        cleanup()
      }, POLL_TIMEOUT_MS)
    },
    onError: () => {
      toast.error("Failed to start poll")
    },
  })

  const isPolling = status === "pending" || status === "processing"

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => pollMutation.mutate()}
      disabled={isPolling || pollMutation.isPending}
    >
      {isPolling ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <RefreshCw className="h-4 w-4" />
      )}
      {isPolling ? "Polling..." : "Poll Now"}
    </Button>
  )
}
