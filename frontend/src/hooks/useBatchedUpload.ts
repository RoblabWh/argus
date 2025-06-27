import { useCallback } from "react";
import { getApiUrl } from "@/api";

type UploadFile = {
  file: File;
};

export function useBatchedUpload(report_id: number) {
    const apiUrl = getApiUrl();
    const uploadUrl = `${apiUrl}/images/report/${report_id}`;
    const uploadBatch = useCallback(
    async (
      files: UploadFile[],
      onProgress: (file: File, percent: number) => void
    ) => {
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        const formData = new FormData();
        files.forEach(({ file }) => formData.append("files", file));

        xhr.upload.addEventListener("progress", (e) => {
          if (e.lengthComputable) {
            const percent = Math.round((e.loaded * 100) / e.total);
            files.forEach(({ file }) => onProgress(file, percent));
          }
        });

        xhr.onload = () => {
          if (xhr.status < 300) {
            resolve(xhr.response);
          } else {
            reject(xhr.response);
          }
        };

        xhr.onerror = () => reject(xhr.response);

        xhr.open("POST", uploadUrl);
        xhr.send(formData);
      });
    },
    []
  );

  return { uploadBatch };
}
