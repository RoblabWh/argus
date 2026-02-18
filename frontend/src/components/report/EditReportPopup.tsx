import { useState, useEffect } from "react"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useUpdateReport } from "@/hooks/reportHooks" // You’ll need to create/adapt this

interface EditReportPopupProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  reportId: number
  initialTitle: string
  initialDescription: string
//   updateReport: (title: string, description: string) => void
}

export function EditReportPopup({
  open,
  onOpenChange,
  reportId,
  initialTitle,
  initialDescription,
//   updateReport,
}: EditReportPopupProps) {
  const [formData, setFormData] = useState({ title: "", description: "" })
  const [formErrors, setFormErrors] = useState<{ title?: string; description?: string }>({})

  const { mutate: updateReport, isPending, error } = useUpdateReport()

  // Prefill when opened or when props change
  useEffect(() => {
    if (open) {
      setFormData({ title: initialTitle, description: initialDescription })
      setFormErrors({})
    }
  }, [open, initialTitle, initialDescription])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
    if (value.trim() !== "") {
      setFormErrors((prev) => ({ ...prev, [name]: undefined }))
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    console.log("Submitting report update:", formData)

    const errors: typeof formErrors = {}
    if (!formData.title.trim()) errors.title = "Title is required"
    if (!formData.description.trim()) errors.description = "Description is required"

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      return
    }

    updateReport(
      { id: reportId, ...formData },
      {
        onSuccess: () => {
          onOpenChange(false)
        //   updateReport(formData.title, formData.description)
        },
        onError: (err) => {
          console.error("Error updating report:", err)
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Edit Report</DialogTitle>
            <DialogDescription>Update the title and description of your report.</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 mt-4">
            <div className="grid gap-3">
              <Label htmlFor="edit-title">Title</Label>
              <Input
                id="edit-title"
                name="title"
                value={formData.title}
                onChange={handleChange}
                className={formErrors.title ? "border-red-500 focus-visible:ring-red-500" : ""}
              />
              {formErrors.title && <p className="text-sm text-red-500">{formErrors.title}</p>}
            </div>

            <div className="grid gap-3">
              <Label htmlFor="edit-description">Description</Label>
              <Input
                id="edit-description"
                name="description"
                value={formData.description}
                onChange={handleChange}
                className={formErrors.description ? "border-red-500 focus-visible:ring-red-500" : ""}
              />
              {formErrors.description && <p className="text-sm text-red-500">{formErrors.description}</p>}
            </div>

            {error && (
              <p className="text-sm text-red-600 mt-2">
                Failed to update report. Please try again later.
              </p>
            )}
          </div>

          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline" type="button">
                Cancel
              </Button>
            </DialogClose>
            <Button disabled={isPending} type="submit">
              {isPending ? "Saving..." : "Save Changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
