import type { Image } from "@/types/image";
import { Card, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { getApiUrl } from "@/api";
import { useState, useMemo, useEffect } from "react";

interface GalleryCardProps {
    images: Image[] | undefined;
    setFilteredImages: (images: Image[]) => void;
    filteredImages?: Image[];
    setSelectedImage: (image: Image | null) => void;
}

type FilterTag = "thermal" | "panoramic" | "regular";

export function GalleryCard({ images, setFilteredImages, filteredImages, setSelectedImage }: GalleryCardProps) {
    const apiUrl = getApiUrl();
    const [search, setSearch] = useState("");
    const [activeTags, setActiveTags] = useState<FilterTag[]>([]);

    const getAvailableTags = (images: Image[]): FilterTag[] => {
        const available: Set<FilterTag> = new Set();

        for (const img of images) {
            if (img.thermal) available.add("thermal");
            if (img.panoramic) available.add("panoramic");
            if (!img.thermal && !img.panoramic) available.add("regular");
        }

        return Array.from(available);
    };
    const availableTags = useMemo(() => getAvailableTags(images || []), [images]);


    const toggleTag = (tag: FilterTag) => {
        setActiveTags((prev) =>
            prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
        );
    };

    const onFilterChange = () => {
        if (!images) return [];

        const filtered = images.filter((image) => {
            const matchesSearch = image.filename.toLowerCase().includes(search.toLowerCase());

            const matchesTag =
                activeTags.length === 0 ||
                activeTags.some((tag) => {
                    if (tag === "thermal") return image.thermal;
                    if (tag === "panoramic") return image.panoramic;
                    if (tag === "regular") return !image.thermal && !image.panoramic;
                    return false;
                });

            return matchesSearch && matchesTag;
        });

        setFilteredImages(filtered.sort((a, b) => {
            const aTime = new Date(a.created_at ?? 0).getTime();
            const bTime = new Date(b.created_at ?? 0).getTime();
            return aTime - bTime;
        }))
    };

    // const filteredImages = useMemo(() => {
    //     if (!images) return [];

    //     const filtered = images.filter((image) => {
    //         const matchesSearch = image.filename.toLowerCase().includes(search.toLowerCase());

    //         const matchesTag =
    //             activeTags.length === 0 ||
    //             activeTags.some((tag) => {
    //                 if (tag === "thermal") return image.thermal;
    //                 if (tag === "panoramic") return image.panoramic;
    //                 if (tag === "regular") return !image.thermal && !image.panoramic;
    //                 return false;
    //             });

    //         return matchesSearch && matchesTag;
    //     });

    //     return filtered.sort((a, b) => {
    //         const aTime = new Date(a.created_at ?? 0).getTime();
    //         const bTime = new Date(b.created_at ?? 0).getTime();
    //         return aTime - bTime;
    //     });
    // }, [images, search, activeTags]);

    useEffect(() => {
        onFilterChange();
    }, [search, activeTags, images]);

    if (!images || images.length === 0) {
        return (
            <Card className="min-w-80 max-w-257 flex-2">
                <CardTitle className="text-lg font-semibold p-4">
                    No Images Available
                </CardTitle>
            </Card>
        );
    }

    const onImageClick = (image: Image) => {
        setSelectedImage(image);
    };

    return (
        <Card className="min-w-80 min-h-40 flex flex-col px-4 py-3 gap-2">
            <div className="text-lg font-semibold py-2">
                Images
            </div>

            {/* Filters */}
            <div className=" pb-2">
                <div className="flex flex-wrap items-center gap-2">
                    <div className="relative sm:w-auto flex-grow min-w-[180px]">
                        <Input
                            placeholder="Search by filename..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="pr-6"
                        />
                        {search && (
                            <button
                                type="button"
                                onClick={() => setSearch("")}
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground text-sm"
                                aria-label="Clear search"
                            >
                                ×
                            </button>
                        )}
                    </div>


                    {/* Filter Buttons */}
                    <div className="flex flex-wrap gap-2">
                        {(["thermal", "panoramic", "regular"] as FilterTag[])
                            .filter((tag) => availableTags.includes(tag))
                            .map((tag) => {
                                const isActive = activeTags.includes(tag);

                                return (
                                    <button
                                        key={tag}
                                        onClick={() => toggleTag(tag)}
                                        className={`flex items-center gap-1 px-3 py-1.5 text-sm rounded-full border transition
                                            ${isActive
                                                ? "bg-primary text-primary-foreground border-primary"
                                                : "bg-muted text-muted-foreground border border-input hover:bg-accent hover:text-accent-foreground"}
                                            `}
                                    >
                                        <span className="capitalize">{tag}</span>
                                        {isActive && (
                                            <span className="ml-1 text-xs leading-none">×</span>
                                        )}
                                    </button>
                                );
                            })}
                    </div>

                    {/* Reset Button */}
                    {(activeTags.length > 0 || search.length > 0) && (
                        <Button variant="ghost" onClick={() => { setActiveTags([]); setSearch(""); }}>
                            Reset
                        </Button>
                    )}
                </div>
            </div>

            {/* Gallery Grid */}
            <div className="overflow-auto grow grid grid-cols-[repeat(auto-fit,minmax(130px,1fr))] gap-4 flex-1">
                {filteredImages.map((image) => (
                    <Card
                        key={"gallery-img-" + image.id}
                        className="relative p-0 flex flex-col justify-between items-center h-full gap-0 rounded-sm"
                        onClick={() => onImageClick(image)}
                    >
                        <div className="w-full overflow-hidden p-1">
                            <img
                                src={`${apiUrl}/${image.thumbnail_url}`}
                                alt={image.filename}
                                className="w-full h-full object-contain rounded-xs"
                            />
                        </div>

                        <div className="mt-0 w-full p-2 pt-0 pb-1">
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <p className="text-sm mt-1 w-full truncate text-center">
                                        {image.filename}
                                    </p>
                                </TooltipTrigger>
                                <TooltipContent>
                                    <p>{image.filename}</p>
                                </TooltipContent>
                            </Tooltip>
                        </div>
                    </Card>
                ))}
            </div>
        </Card>
    );
}
