import { WatchDetail } from "@/components/watches/watch-detail"

export const dynamic = "force-dynamic"

export default async function WatchDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  return <WatchDetail id={id} />
}
