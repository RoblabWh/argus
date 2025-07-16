import React, { useState, useCallback, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { Progress } from "@/components/ui/progress";
import { useBatchedUpload } from "@/hooks/useBatchedUpload";
import type { Report } from "@/types/report";
import { getApiUrl } from "@/api";
import { useDeleteImage } from "@/hooks/useImageMutations";
import { GalleryImage } from "@/components/report/upload/UploadGalleryImage";
import { ImageUp } from "lucide-react";

type UploadFile = {
  file?: File;
  preview?: string;
  progress?: number;
  isExisting?: boolean;
  imageObject?: {
    id: number;
    filename: string;
    thumbnail_url: string;
  };
};

type Props = {
  report: Report;
};

export const UploadArea: React.FC<Props> = ({ report }) => {
  const apiUrl = getApiUrl();
  const { uploadBatch } = useBatchedUpload(report.report_id);
  const deleteImageMutation = useDeleteImage();

  const [uploads, setUploads] = useState<UploadFile[]>([]);

    // Load existing images into unified list to show them with new uploads
  useEffect(() => {
    if (report.mapping_report?.images) {
      const existingUploads: UploadFile[] = report.mapping_report.images.map((img) => ({
        imageObject: img,
        isExisting: true,
      }));
      setUploads(existingUploads);
    }
  }, [report]);

  const uploadingOnly = uploads.filter((u) => !u.isExisting);
  const overallProgress =
  uploadingOnly.length === 0
    ? 0
    : Math.round(
        uploadingOnly.reduce((sum, u) => sum + (u.progress ?? 0), 0) /
        uploadingOnly.length
      );
      

  // Handle new image drop/upload
  const handleDrop = useCallback(
    (acceptedFiles: File[]) => {
      const newUploads: UploadFile[] = acceptedFiles.map((file) => ({
        file,
        preview: URL.createObjectURL(file),
        progress: 0,
      }));

      // Add new uploads at the end (or front if you prefer)
      setUploads((prev) => [...prev, ...newUploads]);

      const batchSize = 12;

      const uploadInBatches = async () => {
        for (let i = 0; i < newUploads.length; i += batchSize) {
          const batch = newUploads.slice(i, i + batchSize);

          await uploadBatch(batch, (file, percent) => {
            setUploads((prev) =>
              prev.map((u) =>
                u.file === file ? { ...u, progress: percent } : u
              )
            );
          }).then((results) => {
            setUploads((prev) =>
              prev.map((u) => {
                const match = results.find(
                  (r) =>
                    r.status === "success" &&
                    r.image_object?.filename === u.file?.name
                );
                return match && match.image_object
                  ? {
                      ...u,
                      imageObject: match.image_object,
                      preview: undefined,
                      file: undefined,
                      progress: 100,
                    }
                  : u;
              })
            );
          });
        }
      };

      uploadInBatches();
    },
    [uploadBatch]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleDrop,
    accept: { "image/*": [] },
    multiple: true,
  });

  // 3. Delete handler
  const handleDelete = (imageId: number) => {
    deleteImageMutation.mutate(imageId, {
      onSuccess: () => {
        setUploads((prev) =>
          prev.filter((u) => u.imageObject?.id !== imageId)
        );
      },
    });
  };

  return (
    <div>
      <div
      className="border-2 border-dashed p-4 rounded-xl text-center bg-white cursor-pointer hover:bg-white/50 dark:bg-gray-800 hover:dark:bg-gray-700 transition-colors"
        {...getRootProps()}
      >
        <input {...getInputProps()} />
        <ImageUp className="mx-auto mb-2 w-8 h-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          {isDragActive
            ? "Drop images here..."
            : "Drag and drop or click to select images"}
        </p>

        {uploadingOnly.length > 0 && (
          <div className="my-4">
            <p className="text-sm mb-1">
              {overallProgress === 100 ? "Upload Finished" : "Uploading..."}
              </p>
            <Progress value={overallProgress} />
          </div>
        )}
      </div>

      <div className="grid gap-4 mt-4 grid-cols-[repeat(auto-fill,minmax(180px,1fr))]">
        {uploads.map((upload, index) => (
          
          <GalleryImage
            key={index}
            src={
              upload.imageObject
                ? `${apiUrl}/${upload.imageObject.thumbnail_url}`
                : upload.preview!
            }
            filename={upload.imageObject?.filename}
            onDelete={
              upload.imageObject
                ? () => handleDelete(upload.imageObject!.id)
                : undefined
            }
            showDelete={!!upload.imageObject}
          >
            {!upload.isExisting && (
              <Progress value={upload.progress} className="w-full mt-2" />
            )}
          </GalleryImage>

        ))}
      </div>
    </div>
  );
};
