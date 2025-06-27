import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getImages, getImage, deleteImage } from "@/api";

const useImages = (reportId: number) => 
  useQuery({
    queryKey: ["images", reportId],
    queryFn: () => getImages(reportId),
    enabled: !!reportId,
  });

const useImage = (imageId: number) => 
  useQuery({
    queryKey: ["image", imageId],
    queryFn: () => getImage(imageId),
    enabled: !!imageId,
  });

const useDeleteImage = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (imageId: number) => deleteImage(imageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["report"] });
    },
  });
};

export { useImages, useImage, useDeleteImage };
