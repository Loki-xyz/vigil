import { z } from "zod"

export const watchSchema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  watch_type: z.enum(["entity", "topic", "act"]),
  query_terms: z.string().min(1, "Query terms are required"),
  court_filter: z.array(z.string()),
  polling_interval_minutes: z.number().min(120),
})

export type WatchFormValues = z.infer<typeof watchSchema>

export const QUERY_PLACEHOLDERS: Record<string, string> = {
  entity: 'e.g., "Amazon Web Services" or "Reliance Industries"',
  topic: 'e.g., "DPDP Act data privacy" or "DTAA Mauritius"',
  act: 'e.g., "Information Technology Act" or "Companies Act 2013"',
}
