/**
 * BBoxCrop — pure-CSS thumbnail that crops a full source image down to a detection's
 * bounding box, scaled into a uniform square. No canvas, no server-side cropping.
 *
 * A fixed-size `overflow:hidden` square holds an absolutely-positioned full <img>. The
 * image is scaled so the bbox's longest side fits `thumbSize`, then translated so the bbox
 * lands centered inside the square. The container's overflow does the actual clipping; the
 * <img> overflows it on all sides. Aspect ratio is preserved (the box is letterboxed).
 *
 * `loading="lazy"` matters — a cluster can reference many large drone images (5472×3648);
 * the browser only fetches images for thumbnails near the viewport, and HTTP-caches the same
 * URL so N crops from one photo cost a single download.
 */
interface BBoxCropProps {
    /** Full source image URL */
    imageUrl: string;
    /** Intrinsic source image dimensions (px) — required for the offset math */
    imageWidth: number;
    imageHeight: number;
    /** Bounding box in source-image pixels: [x, y, w, h] */
    bbox: [number, number, number, number];
    /** Side length of the square thumbnail (px) */
    thumbSize: number;
    alt?: string;
    className?: string;
    onClick?: () => void;
}

export function BBoxCrop({
    imageUrl,
    imageWidth,
    imageHeight,
    bbox,
    thumbSize,
    alt,
    className,
    onClick,
}: BBoxCropProps) {
    const [bx, by, bw, bh] = bbox;

    const scale = thumbSize / Math.max(bw, bh, 1);   // longest bbox side → thumbSize
    const scaledW = imageWidth * scale;               // render whole image at that scale
    const scaledH = imageHeight * scale;
    const offsetX = -bx * scale + (thumbSize - bw * scale) / 2;   // shift bbox to origin, then center
    const offsetY = -by * scale + (thumbSize - bh * scale) / 2;

    return (
        <div
            className={`relative overflow-hidden rounded-sm bg-muted ${onClick ? "cursor-pointer" : ""} ${className ?? ""}`}
            style={{ width: thumbSize, height: thumbSize }}
            onClick={onClick}
        >
            <img
                src={imageUrl}
                alt={alt}
                loading="lazy"
                draggable={false}
                style={{
                    position: "absolute",
                    width: scaledW,
                    height: scaledH,
                    left: offsetX,
                    top: offsetY,
                    maxWidth: "none",
                }}
            />
        </div>
    );
}
