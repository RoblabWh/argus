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
import { useEditGroup } from "@/hooks/groupHooks" // You’ll need to create/adapt this

interface EditGroupPopupProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  groupId: number
  initialName: string
  initialDescription: string
//   updateGroup: (name: string, description: string) => void
}

export function EditGroupPopup({
  open,
  onOpenChange,
  groupId,
  initialName,
  initialDescription,
//   updateGroup,
}: EditGroupPopupProps) {
  const [formData, setFormData] = useState({ name: "", description: "" })
  const [formErrors, setFormErrors] = useState<{ name?: string; description?: string }>({})

  const { mutate: updateGroup, isPending, error } = useEditGroup()

  // Prefill when opened or when props change
  useEffect(() => {
    if (open) {
      setFormData({ name: initialName, description: initialDescription })
      setFormErrors({})
    }
  }, [open, initialName, initialDescription])

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
    if (!formData.name.trim()) errors.name = "Name is required"
    if (!formData.description.trim()) errors.description = "Description is required"

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      return
    }

    updateGroup(
      { id: groupId, ...formData },
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
      <form className="hidden">
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Edit Report</DialogTitle>
            <DialogDescription>Update the title and description of your report.</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="grid gap-3">
              <Label htmlFor="title">Title</Label>
              <Input
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                className={formErrors.name ? "border-red-500 focus-visible:ring-red-500" : ""}
              />
              {formErrors.name && <p className="text-sm text-red-500">{formErrors.name}</p>}
            </div>

            <div className="grid gap-3">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
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

          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" type="button">
                Cancel
              </Button>
            </DialogClose>
            <Button disabled={isPending} type="submit" onClick={handleSubmit}>
              {isPending ? "Saving..." : "Save Changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </form>
    </Dialog>
  )
}
