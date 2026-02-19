"use client"

import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { supabase } from "@/lib/supabase/client"
import type { PollRequest, PollRequestStatus } from "@/lib/supabase/types"
import { Button } from "@/components/ui/button"
import { Loader2, RefreshCw } from "lucide-react"
import { toast } from "sonner"

export function PollNowButton({ watchId }: { watchId: string }) {
  const [status, setStatus] = useState<PollRequestStatus | null>(null)
  const queryClient = useQueryClient()

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
              supabase.removeChannel(channel)
            } else if (newStatus === "failed") {
              toast.error("Poll failed")
              setStatus(null)
              supabase.removeChannel(channel)
            }
          }
        )
        .subscribe()
    },
    onError: () => {
      toast.error("Failed to start poll")
    },
  })

  const isPolling = status === "pending" || status === "processing"

  return (
    <Button
      variant="outline"
      size="xs"
      onClick={() => pollMutation.mutate()}
      disabled={isPolling || pollMutation.isPending}
    >
      {isPolling ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <RefreshCw className="h-3 w-3" />
      )}
      {isPolling ? "Polling..." : "Poll Now"}
    </Button>
  )
}
