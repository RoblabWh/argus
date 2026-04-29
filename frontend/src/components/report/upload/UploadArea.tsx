import React, { useState, useCallback, useEffect, useRef } from "react";
import { useDropzone } from "react-dropzone";
import { Progress } from "@/components/ui/progress";
import { useUnifiedUpload } from "@/hooks/useUnifiedUpload";
import type { Report } from "@/types/report";
import type { UploadFile } from "@/types/image";
import type { UploadSummary, VideoUploadResult } from "@/types/reconstruction";
import { getApiUrl } from "@/api";
import { useDeleteImage, useImages } from "@/hooks/imageHooks";
import { GalleryImage } from "@/components/report/upload/UploadGalleryImage";
import { ImageUp, ImagePlus, Film, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

type UploadAreaProps = {
  report: Report;
  uploads: UploadFile[];
  setUploads: React.Dispatch<React.SetStateAction<UploadFile[]>>;
  setIsUploading?: React.Dispatch<React.SetStateAction<boolean>>;
  onUploadComplete?: (summary: UploadSummary) => void;
  /** Passed from parent so UploadArea can adapt its UI for the known report type */
  detectedType?: string;
};

export const UploadArea: React.FC<UploadAreaProps> = ({
  report,
  uploads,
  setUploads,
  setIsUploading,
  onUploadComplete,
  detectedType,
}) => {
  const apiUrl = getApiUrl();
  const { uploadAll } = useUnifiedUpload(report.report_id);
  const deleteImageMutation = useDeleteImage();
  const { data: images } = useImages(report.report_id);
  const [busy, setBusy] = useState(false);
  const [videoConfirmed, setVideoConfirmed] = useState<VideoUploadResult | null>(null);
  // Tracks a video file that is currently being uploaded (progress 0–100)
  const [videoUploading, setVideoUploading] = useState<{ file: File; progress: number } | null>(null);
  const autoHideRef = useRef<number | null>(null);

  // Pre-populate video confirmation when re-editing an existing reconstruction report
  useEffect(() => {
    if (
      report.type === "reconstruction_360" &&
      report.reconstruction_report?.video_path &&
      !videoConfirmed
    ) {
      const pathParts = report.reconstruction_report.video_path.split("/");
      const filename = pathParts[pathParts.length - 1];
      setVideoConfirmed({ status: "uploaded", filename, message: null });
    }
  }, [report.type, report.reconstruction_report?.video_path]);

  // Load existing images into unified list
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
    const hasActiveUploads = overallProgress > 0 && overallProgress < 100;
    const hasVideoUploading = videoUploading !== null;
    if (setIsUploading) {
      setIsUploading(hasActiveUploads || hasVideoUploading);
    }
  }, [overallProgress, videoUploading]);

  const handleDrop = useCallback(
    (acceptedFiles: File[]) => {
      const videoFiles = acceptedFiles.filter((f) => f.type.startsWith("video/"));
      const imageFiles = acceptedFiles.filter((f) => !f.type.startsWith("video/"));

      // Optimistic image entries (show placeholders immediately)
      if (imageFiles.length > 0) {
        const newUploads: UploadFile[] = imageFiles.map((file) => ({ file, progress: 0 }));
        setUploads((prev) => [...prev, ...newUploads]);
      }

      // Track video upload progress
      if (videoFiles.length > 0) {
        setVideoUploading({ file: videoFiles[0], progress: 0 });
      }

      const allFiles = acceptedFiles.map((file) => ({ file }));

      const doUpload = async () => {
        const summary = await uploadAll(allFiles, (file, percent) => {
          if (file.type.startsWith("video/")) {
            setVideoUploading((prev) => (prev ? { ...prev, progress: percent } : null));
          } else {
            setUploads((prev) =>
              prev.map((u) => (u.file === file ? { ...u, progress: percent } : u))
            );
          }
        });

        // Update image uploads with server response
        setUploads((prev) =>
          prev.map((u) => {
            const match = summary.images.find(
              (r) => r.status === "success" && r.image_object?.filename === u.file?.name
            );
            return match && match.image_object
              ? {
                  ...u,
                  imageObject: match.image_object as UploadFile["imageObject"],
                  preview: undefined,
                  file: undefined,
                  progress: 100,
                }
              : u;
          })
        );

        // Handle video result — clear in-progress, set confirmed
        if (videoFiles.length > 0) {
          setVideoUploading(null);
          if (summary.video?.status === "uploaded") {
            setVideoConfirmed(summary.video);
          }
        }

        // Show warnings as toasts
        summary.warnings?.forEach((msg) => toast.warning(msg));

        // Notify parent
        if (onUploadComplete) onUploadComplete(summary);
      };

      doUpload();
      setBusy(false);
    },
    [uploadAll, onUploadComplete]
  );

  // Adapt accept + text based on current state
  const isReconstructionMode = detectedType === "reconstruction_360";
  const isMappingMode = detectedType === "mapping";
  const hasImages = uploads.some((u) => u.isExisting || !!u.imageObject);

  // Accept rules: mapping mode (with images already) → images only; default → images + video
  const dropzoneAccept =
    isMappingMode && hasImages
      ? { "image/*": [] }
      : { "image/*": [], "video/*": [] };

  const dropzoneText = (() => {
    if (isMappingMode && hasImages) return "Add more images";
    return "Drag and drop images or a 360° video";
  })();

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleDrop,
    accept: dropzoneAccept,
    multiple: true,
    onFileDialogOpen: () => {
      setBusy(true);
      if (autoHideRef.current) window.clearTimeout(autoHideRef.current);
      autoHideRef.current = window.setTimeout(() => setBusy(false), 60000);
    },
    onFileDialogCancel: () => {
      setBusy(false);
      if (autoHideRef.current) window.clearTimeout(autoHideRef.current);
    },
    useFsAccessApi: true,
  });

  const handleDelete = (imageId: number) => {
    deleteImageMutation.mutate(imageId, {
      onSuccess: () => {
        setUploads((prev) => prev.filter((u) => u.imageObject?.id !== imageId));
      },
    });
  };

  return (
    <div>
      {/* Video uploading in progress */}
      {videoUploading && (
        <div className="flex items-center gap-3 mb-4 p-3 rounded-lg border border-border bg-muted/30">
          <Film className="w-5 h-5 text-muted-foreground shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{videoUploading.file.name}</p>
            <Progress value={videoUploading.progress} className="mt-1.5" />
          </div>
          <span className="text-xs text-muted-foreground shrink-0">
            {videoUploading.progress}%
          </span>
        </div>
      )}

      {/* Video confirmation banner (after successful upload) */}
      {videoConfirmed && !videoUploading && (
        <div className="flex items-center gap-3 mb-4 p-3 rounded-lg border border-green-300 bg-green-50 dark:bg-green-950 dark:border-green-800">
          <Film className="w-5 h-5 text-green-600 dark:text-green-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-green-800 dark:text-green-200 truncate">
              {videoConfirmed.filename}
            </p>
            <p className="text-xs text-green-600 dark:text-green-400">360° video uploaded</p>
          </div>
          <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400 shrink-0" />
        </div>
      )}

      {/* Drop zone — hidden when video is confirmed (reconstruction locked in) */}
      {!isReconstructionMode || !videoConfirmed ? (
        <div
          className="border-2 border-dashed p-4 rounded-xl text-center bg-white cursor-pointer hover:bg-white/50 dark:bg-gray-800 hover:dark:bg-gray-700 transition-colors"
          {...getRootProps()}
        >
          <input {...getInputProps()} />
          <ImagePlus className="mx-auto mb-2 w-8 h-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            {isDragActive ? "Drop files here..." : dropzoneText}
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
      ) : null}

      {/* Image grid */}
      {uploads.length > 0 && (
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
              showWarning={!!upload.imageObject && !upload.imageObject.mapping_data}
            >
              {!upload.isExisting && (
                <Progress value={upload.progress} className="w-full mt-2" />
              )}
            </GalleryImage>
          ))}
        </div>
      )}

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

function BusyOverlay({
  show,
  message = "Files are being prepared for upload…",
  icon = "clock",
}: {
  show: boolean;
  message?: string;
  icon?: "clock" | "spinner" | "hourglass";
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

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
                  className={`h-8 w-8 ${icon === "spinner" ? "animate-spin" : ""}`}
                />
              </div>
              <div className="min-w-0">
                <h2 className="text-lg font-semibold leading-tight">Preparing files…</h2>
                <p className="text-sm text-zinc-600 dark:text-zinc-400">{message}</p>
              </div>
            </div>
            <div className="px-6 pb-6">
              <div className="w-full h-2 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
                <motion.div
                  className="h-full w-1/3 bg-zinc-800 dark:bg-zinc-100"
                  initial={{ x: "-100%" }}
                  animate={{ x: ["-100%", "150%"] }}
                  transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
                />
              </div>
              <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">
                This may take a moment for very large selections. You can keep this tab in the
                foreground.
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
