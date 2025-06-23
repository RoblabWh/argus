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
import { useState } from "react"
import { useCreateGroup } from "@/hooks/groupHooks" // Adjust the import based on your project structure


interface NewGroupPopupProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function NewGroupPopup({ open, onOpenChange }: NewGroupPopupProps) {
    const [formData, setFormData] = useState({ name: "", description: "" }); 
      const [formErrors, setFormErrors] = useState<{ name?: string; description?: string }>({})
    const { mutate: createGroup, isPending, error } = useCreateGroup();


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
        if (!formData.name.trim()) errors.name = "Name is required"
        if (!formData.description.trim()) errors.description = "Description is required"

        if (Object.keys(errors).length > 0) {
            setFormErrors(errors)
            return
        }

        createGroup(formData, {
            onSuccess: () => {
                resetFormData();
                onOpenChange(false);
            },
            onError: (error) => {
                console.error("Error creating group:", error);
            },
        });
    };


    // Reset form data and errors
    const resetFormData = () => {
        setFormData({ name: "", description: "" })
        setFormErrors({});
    }
  
    
    return (
    <Dialog open={open} onOpenChange={onOpenChange}>
        <form onSubmit={handleSubmit}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>Create New Group</DialogTitle>
                    <DialogDescription>
                        Fill in the details to create a new group.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4">
                    <div className="grid gap-3">
                        <Label htmlFor="name">Name</Label>
                        <Input
                            id="name"
                            name="name"
                            onChange={handleChange}
                            value={formData.name}
                            className={formErrors.name ? "border-red-500 focus-visible:ring-red-500" : ""}
                        />
                        {formErrors.name && <p className="text-sm text-red-500">{formErrors.name}</p>}
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
                    <Button onClick={handleSubmit}>Create Group</Button>
                </DialogFooter>
            </DialogContent>
        </form>
    </Dialog>
  )
}
