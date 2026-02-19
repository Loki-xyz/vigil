import { Header } from "@/components/layout/header"
import { JudgmentTable } from "@/components/judgments/judgment-table"

export const dynamic = "force-dynamic"

export default function JudgmentsPage() {
  return (
    <div className="space-y-6">
      <Header
        title="Judgments"
        description="All matched judgments across your watches"
      />
      <JudgmentTable />
    </div>
  )
}
