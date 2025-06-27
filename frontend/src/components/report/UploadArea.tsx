import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Progress } from "@/components/ui/progress";
import { Card } from "@/components/ui/card";
import { useBatchedUpload } from "@/hooks/useBatchedUpload";
import type { Report } from "@/types/report";
import { getApiUrl } from "@/api";
import { Button } from "../ui/button";
import { useDeleteImage } from "@/hooks/useImageMutations";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";



type UploadFile = {
  file: File;
  preview: string;
  progress: number;
};

type Props = {
  report: Report;
};

export const UploadArea: React.FC<Props> = ({ report }) => {
  const [uploads, setUploads] = useState<UploadFile[]>([]);
  const { uploadBatch } = useBatchedUpload(report.report_id);
  const deleteImageMutation = useDeleteImage();
  const apiUrl = getApiUrl();
  const queryClient = useQueryClient();


  const overallProgress =
  uploads.length === 0
    ? 0
    : Math.round(
        uploads.reduce((sum, u) => sum + u.progress, 0) / uploads.length
      );

  useEffect(() => {
    const allDone = uploads.length > 0 && uploads.every(u => u.progress === 100);
    if (allDone) {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["report"] });
        setUploads([]);
      }, 500);
    }
  }, [uploads, queryClient]);

  const handleDrop = useCallback((acceptedFiles: File[]) => {
    const newUploads: UploadFile[] = acceptedFiles.map(file => ({
      file,
      preview: URL.createObjectURL(file),
      progress: 0
    }));
    setUploads(prev => [...prev, ...newUploads]);

    const batchSize = 10;
    const uploadInBatches = async () => {
      for (let i = 0; i < newUploads.length; i += batchSize) {
        const batch = newUploads.slice(i, i + batchSize);

        await uploadBatch(batch, (file, percent) => {
          setUploads(prev =>
            prev.map(u =>
              u.file === file ? { ...u, progress: percent } : u
            )
          );
        });
      }
    };

    uploadInBatches();
  }, [uploadBatch]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleDrop,
    accept: { "image/*": [] },
    multiple: true
  });



  return (
    <>
    <div {...getRootProps()} className="border-2 border-dashed p-4 rounded-xl text-center bg-muted cursor-pointer hover:bg-muted/50">
      <input {...getInputProps()} />
      <p>{isDragActive ? "Drop images here..." : "Drag and drop or click to select images"}</p>
      {uploads.length > 0 && (
        <div className="my-4">
          <p className="text-sm mb-1">Overall Progress</p>
          <Progress value={overallProgress} />
        </div>
      )}
      <div className="grid grid-cols-4 gap-4 mt-4">
        {uploads.map((upload, index) => (
          <Card key={index} className="p-2 flex flex-col items-center">
            <img src={upload.preview} alt="preview" className="w-full h-24 object-cover rounded-md" />
            <Progress value={upload.progress} className="w-full mt-2" />
          </Card>
        ))}
      </div>
    </div>
    <div className="mt-6">

      { report.mapping_report && report.mapping_report.images.length > 0 && (
        <div className="mt-4">
          <h3 className="text-lg font-semibold">Existing Images</h3>
          <div className="grid grid-cols-4 gap-4 mt-2">
            {report.mapping_report.images.map((image, index) => (
              <Card key={index} className="p-2 flex flex-col items-center">
                <img src={apiUrl+"/"+image.thumbnail_url} alt={`existing-${index}`} className="w-full h-24 object-cover rounded-md" />
                <p className="text-sm mt-2">{image.filename}</p>
                <Button variant="destructive" className="mt-2" onClick={() => deleteImageMutation.mutate(image.id)}>
                    Delete
                </Button>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
    </>
  );
};
