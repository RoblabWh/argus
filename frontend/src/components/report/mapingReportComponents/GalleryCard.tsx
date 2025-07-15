import type { Image } from "@/types/image";
import { Card, CardTitle } from "@/components/ui/card";
import { Drone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getApiUrl } from "@/api";

interface GalleryCardProps {
    images: Image[] | undefined;
}

export function GalleryCard({ images }: GalleryCardProps) {
    const apiUrl = getApiUrl();

    if (!images || images.length === 0) {
        return (
            <Card className="min-w-80 max-w-257 flex-2">
                <CardTitle className="text-lg font-semibold p-4">
                    No Images Available
                </CardTitle>
            </Card>
        );
    }

    return (
        <Card className="min-w-80 max-w-257 min-h-40  flex flex-col">
            <CardTitle className="text-lg font-semibold p-4">
                Gallery
            </CardTitle>

            <div className="p-4 overflow-auto grow grid grid-cols-[repeat(auto-fit,minmax(130px,1fr))] gap-4">
                {images.map((image, index) => (
                    <img
                        key={index}
                        src={`${apiUrl}/${image.thumbnail_url}`}
                        alt={image.filename}
                        className="w-full h-auto rounded-md"
                    />
                ))}
            </div>
        </Card>
    );
}