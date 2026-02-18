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
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useCallback, useEffect, useState } from "react"
import { useCreateReport } from "@/hooks/reportHooks"
import { useImportReport } from "@/hooks/reportHooks"
import { useDropzone } from "react-dropzone"
import { Upload, FileArchive, Loader2 } from "lucide-react"


interface NewReportPopupProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  groupId: number;
  groupName: string;
}

export function NewReportPopup({ open, onOpenChange, groupId, groupName }: NewReportPopupProps) {
    const [tab, setTab] = useState("new");
    const [formData, setFormData] = useState({ title: "", description: "" });
    const [formErrors, setFormErrors] = useState<{ title?: string; description?: string }>({});
    const { mutate: createReport, isPending, error } = useCreateReport();

    const [importFile, setImportFile] = useState<File | null>(null);
    const { mutate: doImport, isPending: isImporting, error: importError } = useImportReport();

    useEffect(() => {
        if (open) {
            setFormData({ title: "", description: "" });
            setFormErrors({});
            setImportFile(null);
            setTab("new");
        }
    }, [open]);

    // --- New Report tab ---
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target
        setFormData((prev) => ({ ...prev, [name]: value }))
        if (value.trim() !== "") {
            setFormErrors((prev) => ({ ...prev, [name]: undefined }))
        }
    }

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
            onSuccess: () => onOpenChange(false),
            onError: (error) => console.error("Error creating report:", error),
        });
    };

    // --- Import tab ---
    const onDrop = useCallback((accepted: File[]) => {
        if (accepted.length > 0) setImportFile(accepted[0]);
    }, []);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: { "application/zip": [".zip"] },
        maxFiles: 1,
    });

    const handleImport = () => {
        if (!importFile) return;
        doImport({ groupId, file: importFile }, {
            onSuccess: () => onOpenChange(false),
            onError: (err) => console.error("Import error:", err),
        });
    };

    const formatSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    return (
    <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-md">
            <DialogHeader>
                <DialogTitle>Add Report</DialogTitle>
                <DialogDescription>
                    Add a new report for the group: &nbsp;{groupName}
                </DialogDescription>
            </DialogHeader>

            <Tabs value={tab} onValueChange={setTab}>
                <TabsList className="w-full">
                    <TabsTrigger value="new" className="flex-1">New Report</TabsTrigger>
                    <TabsTrigger value="import" className="flex-1">Import</TabsTrigger>
                </TabsList>

                <TabsContent value="new">
                    <form onSubmit={handleSubmit}>
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
                                <p className="text-sm text-red-600">
                                    Failed to create report. Please try again later.
                                </p>
                            )}
                        </div>
                        <DialogFooter className="mt-4">
                            <DialogClose asChild>
                                <Button variant="outline">Cancel</Button>
                            </DialogClose>
                            <Button type="submit" disabled={isPending}>
                                {isPending ? <Loader2 className="animate-spin mr-2 h-4 w-4" /> : null}
                                Create Report
                            </Button>
                        </DialogFooter>
                    </form>
                </TabsContent>

                <TabsContent value="import">
                    <div className="grid gap-4">
                        <div
                            {...getRootProps()}
                            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
                                ${isDragActive ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary/50"}`}
                        >
                            <input {...getInputProps()} />
                            {importFile ? (
                                <div className="flex flex-col items-center gap-2">
                                    <FileArchive className="h-10 w-10 text-primary" />
                                    <p className="font-medium">{importFile.name}</p>
                                    <p className="text-sm text-muted-foreground">{formatSize(importFile.size)}</p>
                                    <p className="text-xs text-muted-foreground">Click or drop to replace</p>
                                </div>
                            ) : (
                                <div className="flex flex-col items-center gap-2">
                                    <Upload className="h-10 w-10 text-muted-foreground" />
                                    <p className="font-medium">Drop a ZIP file here</p>
                                    <p className="text-sm text-muted-foreground">or click to browse</p>
                                </div>
                            )}
                        </div>
                        {importError && (
                            <p className="text-sm text-red-600">
                                {importError instanceof Error ? importError.message : "Import failed. Please try again."}
                            </p>
                        )}
                    </div>
                    <DialogFooter className="mt-4">
                        <DialogClose asChild>
                            <Button variant="outline">Cancel</Button>
                        </DialogClose>
                        <Button onClick={handleImport} disabled={!importFile || isImporting}>
                            {isImporting ? <Loader2 className="animate-spin mr-2 h-4 w-4" /> : null}
                            Import
                        </Button>
                    </DialogFooter>
                </TabsContent>
            </Tabs>
        </DialogContent>
    </Dialog>
  )
}
