import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { Loader2 } from "lucide-react"
import { useGroups } from "@/hooks/groupHooks"
import { useMoveReport } from "@/hooks/reportHooks"

interface MoveReportPopupProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  reportId: number
  reportTitle: string
  currentGroupId: number
}

export function MoveReportPopup({ open, onOpenChange, reportId, reportTitle, currentGroupId }: MoveReportPopupProps) {
  const [selectedGroupId, setSelectedGroupId] = useState<string>("")
  const { data: groups, isLoading } = useGroups()
  const { mutate: doMove, isPending, error } = useMoveReport()

  const handleMove = () => {
    if (!selectedGroupId) return
    doMove({ reportId, groupId: parseInt(selectedGroupId) }, {
      onSuccess: () => onOpenChange(false),
    })
  }

  const availableGroups = groups?.filter(g => g.id !== currentGroupId) ?? []

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) setSelectedGroupId(""); onOpenChange(o); }}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Move Report</DialogTitle>
          <DialogDescription>
            Move "{reportTitle}" to a different group.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading groups...</p>
        ) : availableGroups.length === 0 ? (
          <p className="text-sm text-muted-foreground">No other groups available.</p>
        ) : (
          <Select value={selectedGroupId} onValueChange={setSelectedGroupId}>
            <SelectTrigger>
              <SelectValue placeholder="Select target group" />
            </SelectTrigger>
            <SelectContent>
              {availableGroups.map(g => (
                <SelectItem key={g.id} value={g.id.toString()}>{g.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {error && (
          <p className="text-sm text-red-600">
            {error instanceof Error ? error.message : "Move failed. Please try again."}
          </p>
        )}

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button onClick={handleMove} disabled={!selectedGroupId || isPending}>
            {isPending ? <Loader2 className="animate-spin mr-2 h-4 w-4" /> : null}
            Move
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
