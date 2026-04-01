import { useCallback } from "react";
import { getUnifiedUploadUrl } from "@/api";
import type { UploadSummary } from "@/types/reconstruction";

type UploadFile = {
  file?: File;
};

const IMAGE_BATCH_SIZE = 12;

/**
 * Unified upload hook — sends files to POST /reports/{id}/upload.
 *
 * Batching strategy:
 *  - Video files (type starts with "video/") go in their own single-file request.
 *  - Image/other files are batched in groups of IMAGE_BATCH_SIZE.
 *
 * Each XHR call returns an UploadSummary. Results are merged across batches
 * into a single combined UploadSummary returned to the caller.
 */
export function useUnifiedUpload(report_id: number) {
  const uploadUrl = getUnifiedUploadUrl(report_id);

  const uploadBatch = useCallback(
    (
      files: UploadFile[],
      onProgress: (file: File, percent: number) => void
    ): Promise<UploadSummary> => {
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        const formData = new FormData();
        files.forEach(({ file }) => file && formData.append("files", file));

        xhr.upload.addEventListener("progress", (e) => {
          if (e.lengthComputable) {
            const percent = Math.round((e.loaded * 100) / e.total);
            files.forEach(({ file }) => file && onProgress(file, percent));
          }
        });

        xhr.onload = () => {
          if (xhr.status < 300) {
            try {
              resolve(JSON.parse(xhr.response) as UploadSummary);
            } catch {
              reject(new Error("Invalid JSON response from upload"));
            }
          } else {
            reject(new Error(`Upload failed: ${xhr.status} ${xhr.response}`));
          }
        };

        xhr.onerror = () => reject(new Error("Upload network error"));
        xhr.open("POST", uploadUrl);
        xhr.send(formData);
      });
    },
    [uploadUrl]
  );

  const uploadAll = useCallback(
    async (
      files: UploadFile[],
      onProgress: (file: File, percent: number) => void
    ): Promise<UploadSummary> => {
      const videoFiles = files.filter((f) => f.file?.type.startsWith("video/"));
      const imageFiles = files.filter((f) => !f.file?.type.startsWith("video/"));

      const combined: UploadSummary = {
        report_type: "unchanged",
        images: [],
        video: null,
        warnings: [],
      };

      // Upload image batches
      for (let i = 0; i < imageFiles.length; i += IMAGE_BATCH_SIZE) {
        const batch = imageFiles.slice(i, i + IMAGE_BATCH_SIZE);
        const summary = await uploadBatch(batch, onProgress);
        combined.images.push(...summary.images);
        if (summary.warnings) combined.warnings.push(...summary.warnings);
        // Last non-"unchanged" report_type wins
        if (summary.report_type !== "unchanged") {
          combined.report_type = summary.report_type;
        }
        if (summary.video) combined.video = summary.video;
      }

      // Upload video in its own batch (only first video is used by backend)
      if (videoFiles.length > 0) {
        const summary = await uploadBatch([videoFiles[0]], onProgress);
        combined.images.push(...summary.images);
        if (summary.warnings) combined.warnings.push(...summary.warnings);
        if (summary.report_type !== "unchanged") {
          combined.report_type = summary.report_type;
        }
        if (summary.video) combined.video = summary.video;
      }

      return combined;
    },
    [uploadBatch]
  );

  return { uploadAll, uploadBatch };
}
