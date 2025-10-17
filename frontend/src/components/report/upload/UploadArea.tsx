import React, { useState, useCallback, useEffect, startTransition, useRef } from "react";
import { useDropzone } from "react-dropzone";
import { Progress } from "@/components/ui/progress";
import { useBatchedUpload } from "@/hooks/useBatchedUpload";
import type { Report } from "@/types/report";
import { getApiUrl } from "@/api";
import { useDeleteImage, useImages } from "@/hooks/imageHooks";
import { GalleryImage } from "@/components/report/upload/UploadGalleryImage";
import { ImageUp, ImagePlus, Upload, CloudUpload } from "lucide-react";
import type { UploadFile } from "@/types/image";

type UploadAreaProps = {
  report: Report;
  uploads: UploadFile[];
  setUploads: React.Dispatch<React.SetStateAction<UploadFile[]>>;
  setIsUploading?: React.Dispatch<React.SetStateAction<boolean>>;
};

export const UploadArea: React.FC<UploadAreaProps> = ({ report, uploads, setUploads, setIsUploading }) => {
  const apiUrl = getApiUrl();
  const { uploadBatch } = useBatchedUpload(report.report_id);
  const deleteImageMutation = useDeleteImage();
  const { data: images } = useImages(report.report_id);
  const [busy, setBusy] = useState(false);
  const autoHideRef = useRef<number | null>(null);


  // Load existing images into unified list to show them with new uploads
  useEffect(() => {
    if (!images || images.length === 0) return;
    const existingUploads: UploadFile[] = images.map((img) => ({
      imageObject: img,
      isExisting: true,
    }));
    setUploads(existingUploads);

  }, [images]);

  const uploadingOnly = uploads.filter((u) => !u.isExisting);
  const overallProgress =
    uploadingOnly.length === 0
      ? 0
      : Math.round(
        uploadingOnly.reduce((sum, u) => sum + (u.progress ?? 0), 0) /
        uploadingOnly.length
      );

  useEffect(() => {
    if (setIsUploading) {
      setIsUploading(overallProgress > 0 && overallProgress < 100);
    }
  }, [overallProgress]);


  // Handle new image drop/upload
  const handleDrop = useCallback(
    (acceptedFiles: File[]) => {
      console.log("Dropped files");
      const newUploads: UploadFile[] = acceptedFiles.map((file) => ({
        file,
        //preview: URL.createObjectURL(file),
        progress: 0,
      }));

      // Add new uploads at the end (or front if you prefer)
      setUploads((prev) => [...prev, ...newUploads]);
      // startTransition(() => {
      //   setUploads((prev) => [...prev, ...newUploads]);
      // });

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
            //startTransition(() => {
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
            //});
          });
        }
      };
      
      uploadInBatches();
      setBusy(false);
    },
    [uploadBatch]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleDrop,
    accept: { "image/*": [] },
    multiple: true,
    onFileDialogOpen: () => {
      setBusy(true);
      // Safety: auto-hide in case the browser never fires onDrop (edge cases)
      if (autoHideRef.current) window.clearTimeout(autoHideRef.current);
      autoHideRef.current = window.setTimeout(() => setBusy(false), 60000);
    },
    onFileDialogCancel: () => {
      setBusy(false);
      if (autoHideRef.current) window.clearTimeout(autoHideRef.current);
    },
    useFsAccessApi: true
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
        <ImagePlus className="mx-auto mb-2 w-8 h-8 text-muted-foreground" />
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
                : undefined
            }
            previewNode={
              !upload.imageObject && (
                <ImageUp className="text-muted-foreground w-12 h-12" />
              )
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
      <BusyOverlay
        show={busy}
        message="Files are getting prepared for upload. Large selections can freeze the system dialog for a bit."
        icon="hourglass"
      />
    </div>
  );
};

import { createPortal } from "react-dom";
import { Loader2, Clock, Hourglass } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

/**
 * BusyOverlay
 * ---------------------------------------------------------------------------
 * Full-screen, accessible overlay to indicate background work while files
 * are being prepared after choosing via the system file picker.
 *
 * Dependencies: tailwindcss, lucide-react, framer-motion
 * Drop this component anywhere in your React tree; it renders in a portal
 * to <body>, so it will appear above everything.
 */
function BusyOverlay({
  show,
  message = "Files are being prepared for upload…",
  icon = "clock", // "clock" | "spinner"
}: {
  show: boolean;
  message?: string;
  icon?: "clock" | "spinner" | "hourglass";
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Prevent background scroll when shown
  useEffect(() => {
    if (!show) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [show]);

  const IconComp = icon === "spinner" ? Loader2 : icon === "hourglass" ? Hourglass : Clock;

  const overlay = (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          aria-live="polite"
          aria-busy={show}
          role="status"
          className="fixed inset-0 z-[9999] bg-black/40 backdrop-blur-sm flex items-center justify-center p-6"
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.98, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="w-full max-w-md rounded-2xl bg-white shadow-2xl ring-1 ring-black/5 dark:bg-zinc-900 dark:text-zinc-100"
          >
            <div className="px-6 pt-6 pb-4 flex items-center gap-4">
              <div className="shrink-0">
                <IconComp
                  aria-hidden
                  className={`h-8 w-8 ${icon === "spinner" ? "animate-spin" : ""
                    }`}
                />
              </div>
              <div className="min-w-0">
                <h2 className="text-lg font-semibold leading-tight">
                  Preparing files…
                </h2>
                <p className="text-sm text-zinc-600 dark:text-zinc-400">
                  {message}
                </p>
              </div>
            </div>
            <div className="px-6 pb-6">
              <div className="w-full h-2 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
                {/* Indeterminate bar */}
                <motion.div
                  className="h-full w-1/3 bg-zinc-800 dark:bg-zinc-100"
                  initial={{ x: "-100%" }}
                  animate={{ x: ["-100%", "150%"] }}
                  transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
                />
              </div>
              <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">
                This may take a moment for very large selections. You can keep this
                tab in the foreground.
              </p>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  if (!mounted) return null;
  return createPortal(overlay, document.body);
}
