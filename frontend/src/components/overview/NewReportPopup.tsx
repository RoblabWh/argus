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
import { useEffect, useState } from "react"
import { useCreateReport } from "@/hooks/reportHooks" // Adjust the import based on your project structure


interface NewReportPopupProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  groupId: number;
  groupName: string; // Optional, if you want to display the group name in the dialog
}

export function NewReportPopup({ open, onOpenChange, groupId, groupName }: NewReportPopupProps) {
    const [formData, setFormData] = useState({ title: "", description: "" });
    const [formErrors, setFormErrors] = useState<{ title?: string; description?: string }>({});
    const { mutate: createReport, isPending, error } = useCreateReport();

    useEffect(() => {
        if (open) {
            resetFormData(); // Reset form data when dialog opens
        }
    }, [open]);


    // Handle input changes
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target
        setFormData((prev) => ({ ...prev, [name]: value }))
        
        if (value.trim() !== "") {
            setFormErrors((prev) => ({ ...prev, [name]: undefined })) // Clear field error on change
        }
    }


    // Handle form submission
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        const errors: typeof formErrors = {}
        if (!formData.title.trim()) errors.title = "Title is required"
        if (!formData.description.trim()) errors.description = "Description is required"

        if (Object.keys(errors).length > 0) {
            setFormErrors(errors)
            return
        }

        createReport({ ...formData, group_id: groupId }, {
            onSuccess: () => {
                resetFormData();
                onOpenChange(false);
            },
            onError: (error) => {
                console.error("Error creating report:", error);
            },
        });
    };


    // Reset form data and errors
    const resetFormData = () => {
        setFormData({ title: "", description: "" })
        setFormErrors({}); 
    }
  

    return (
    <Dialog open={open} onOpenChange={onOpenChange}>
        <form onSubmit={handleSubmit}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>Create New Report</DialogTitle>
                    <DialogDescription>
                        Add a new report for the group: &nbsp;{groupName}
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4">
                    <div className="grid gap-3">
                        <Label htmlFor="title">Title</Label>
                        <Input
                            id="title"
                            name="title"
                            onChange={handleChange}
                            value={formData.title}
                            className={formErrors.title ? "border-red-500 focus-visible:ring-red-500" : ""}
                        />
                        {formErrors.title && <p className="text-sm text-red-500">{formErrors.title}</p>}
                    </div>
                    <div className="grid gap-1">
                        <Label htmlFor="description">Description</Label>
                        <Input
                            id="description"
                            name="description"
                            onChange={handleChange}
                            value={formData.description}
                            className={formErrors.description ? "border-red-500 focus-visible:ring-red-500" : ""}
                        />
                        {formErrors.description && <p className="text-sm text-red-500">{formErrors.description}</p>}
                    </div>
                {error && (
                    <p className="text-sm text-red-600 mt-2">
                        Failed to create group. Please try again later.
                    </p>
                )}
                </div>
                <DialogFooter>
                    <DialogClose asChild>
                        <Button variant="outline">Cancel</Button>
                    </DialogClose>
                    <Button onClick={handleSubmit}>Create Report</Button>
                </DialogFooter>
            </DialogContent>
        </form>
    </Dialog>
  )
}
