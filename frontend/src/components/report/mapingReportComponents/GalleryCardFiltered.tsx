import React, { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { X, Filter as FilterIcon, Thermometer, Info } from "lucide-react";
import { getApiUrl } from "@/api";
import type { ImageBasic } from "@/types/image";
import type { Detection } from "@/types/detection";
import { useImages } from "@/hooks/imageHooks";
import { useDetections } from "@/hooks/detectionHooks";
import { useFilteredImages } from "@/contexts/FileteredImagesContext";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

/**
 * ————————————————————————————————————————————————————————————————
 * Types
 * ————————————————————————————————————————————————————————————————
 */
export type FilterTag = "thermal" | "panoramic" | "regular";

type TempFilters = {
  /** Keep images whose observed MAX temp is >= this value */
  minAtLeast?: number;
  /** Keep images whose observed MIN temp is <= this value */
  maxAtMost?: number;
};
export type GalleryFilters = {
  types: FilterTag[];        // empty => no restriction
  temp: TempFilters;         // only applies to thermal images
  dets: string[];            // empty => no restriction
};

function filterImages(
  images: ImageBasic[] | undefined,
  detections: Detection[] | undefined,
  search: string,
  filters: GalleryFilters,
  thresholds: Record<string, number> = {} // e.g. { person: 0.6, car: 0.5, "*": 0.4 }
): ImageBasic[] {
  if (!images) return [];

  const term = search.toLowerCase().trim();

  // base search (filename)
  let filtered = term
    ? images.filter((img) => img.filename.toLowerCase().includes(term))
    : images;

  const { types, temp, dets } = filters;

  // Build detection index only if we actually filter by detections
  let detIndex: Map<number, Detection[]> | null = null;
  let lowerDets: string[] = [];
  if (dets.length > 0) {
    detIndex = new Map();
    for (const det of detections || []) {
      const arr = detIndex.get(det.image_id);
      if (arr) arr.push(det);
      else detIndex.set(det.image_id, [det]);
    }
    lowerDets = dets.map((d) => d.toLowerCase().trim());
  }

  const thrFor = (cls: string) =>
    thresholds[cls] ?? thresholds[cls.toLowerCase()] ?? thresholds["*"] ?? 0.4;

  filtered = filtered.filter((image) => {
    // 1) Type filters
    const typePass =
      types.length === 0 ||
      types.some((tag) => {
        if (tag === "thermal") return image.thermal;
        if (tag === "panoramic") return image.panoramic;
        if (tag === "regular") return !image.thermal && !image.panoramic;
        return false;
      });
    if (!typePass) return false;

    // 2) Thermal constraints (only if thermal)
    if (image.thermal) {
      // @ts-ignore (runtime shape)
      const td = (image as any).thermal_data;
      const hasTD = td && typeof td.min_temp === "number" && typeof td.max_temp === "number";

      // If temp filters are set but there's no thermal data → exclude
      if ((temp.minAtLeast !== undefined || temp.maxAtMost !== undefined) && !hasTD) return false;

      if (hasTD) {
        if (temp.minAtLeast !== undefined && !(td.max_temp >= temp.minAtLeast)) return false;
        if (temp.maxAtMost !== undefined && !(td.min_temp <= temp.maxAtMost)) return false;
      }
    } else if (temp.minAtLeast !== undefined || temp.maxAtMost !== undefined) {
      // Non-thermal images fail if any thermal filter is set
      return false;
    }

    // 3) Detection filters — OR semantics (any selected class may match)
    if (detIndex) {
      const imageDets = detIndex.get(image.id) ?? [];
      if (imageDets.length === 0) return false;

      const hasAny = lowerDets.some((cls) => {
        const thr = thrFor(cls);
        return imageDets.some(
          (det) =>
            det.class_name.toLowerCase().startsWith(cls) &&
            (typeof det.score === "number" ? det.score >= thr : true)
        );
      });

      if (!hasAny) return false;
    }

    return true;
  });

  // chronological sort
  let sorted = filtered.sort(
    (a, b) => new Date(a.created_at ?? 0).getTime() - new Date(b.created_at ?? 0).getTime()
  );
  return sorted;
}



function getAvailableTags(images: ImageBasic[] | undefined): FilterTag[] {
  if (!images) return [];
  const available: Set<FilterTag> = new Set();
  for (const img of images) {
    if (img.thermal) available.add("thermal");
    if (img.panoramic) available.add("panoramic");
    if (!img.thermal && !img.panoramic) available.add("regular");
  }
  return Array.from(available);
}

function getDatasetTempRange(images: ImageBasic[] | undefined) {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  let count = 0;
  for (const img of images || []) {
    // @ts-ignore — runtime check only
    const td = img.thermal_data as any;
    if (img.thermal && td && typeof td.min_temp === "number" && typeof td.max_temp === "number") {
      min = Math.min(min, td.min_temp);
      max = Math.max(max, td.max_temp);
      count++;
    }
  }
  if (count === 0) return null;
  return { min, max, count };
}

/**
 * ————————————————————————————————————————————————————————————————
 * FiltersPopover — compact filter UI in a popover
 * ————————————————————————————————————————————————————————————————
 */
interface FiltersPopoverProps {
  availableTypes: FilterTag[];
  availableDetectionClasses: string[];
  value: GalleryFilters;
  onChange: (next: GalleryFilters) => void;
  datasetTempRange: { min: number; max: number; count: number } | null;
  tempUnit?: "C" | "F";
  onReset?: () => void;
}

function FiltersPopover({ availableTypes, availableDetectionClasses, value, onChange, datasetTempRange, tempUnit = "C", onReset }: FiltersPopoverProps) {
  const [open, setOpen] = useState(false);
  const [minInput, setMinInput] = useState(value.temp.minAtLeast ?? "");
  const [maxInput, setMaxInput] = useState(value.temp.maxAtMost ?? "");
  const debouncedMin = useDebouncedValue(minInput, 500);
  const debouncedMax = useDebouncedValue(maxInput, 500);

  useEffect(() => {
    const num = debouncedMin === "" ? undefined : Number(debouncedMin);
    setMinAtLeast(num);
  }, [debouncedMin]);

  useEffect(() => {
    const num = debouncedMax === "" ? undefined : Number(debouncedMax);
    setMaxAtMost(num);
  }, [debouncedMax]);

  const allActive = value.types.length === 0; // no restriction === All
  const allActiveDets = value.dets.length === 0; // no restriction === All

  const setTypes = (types: FilterTag[]) => onChange({ ...value, types });
  const setDetectionClasses = (dets: string[]) => onChange({ ...value, dets });

  const toggleType = (tag: FilterTag) => {
    // If All is active, clicking a single tag makes that the only active tag
    if (allActive) return setTypes([tag]);
    // Otherwise toggle membership
    const exists = value.types.includes(tag);
    const next = exists ? value.types.filter((t) => t !== tag) : [...value.types, tag];
    // If user deselects everything, fall back to All (empty array)
    setTypes(next.length === 0 ? [] : next);
  };

  const toggleDetectionClass = (cls: string) => {
    // If All is active, clicking a single class makes that the only active class
    if (allActiveDets) return setDetectionClasses([cls]);
    // Otherwise toggle membership
    const exists = value.dets.includes(cls);
    const next = exists ? value.dets.filter((c) => c !== cls) : [...value.dets, cls];
    setDetectionClasses(next.length === 0 ? [] : next);
  };

  const activateAll = () => setTypes([]);

  const setMinAtLeast = (v?: number) => onChange({ ...value, temp: { ...value.temp, minAtLeast: v } });
  const setMaxAtMost = (v?: number) => onChange({ ...value, temp: { ...value.temp, maxAtMost: v } });

  const minBound = datasetTempRange?.min ?? 0;
  const maxBound = datasetTempRange?.max ?? 100;

  const minToggle = value.temp.minAtLeast !== undefined;
  const maxToggle = value.temp.maxAtMost !== undefined;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2 h-9">
          <FilterIcon className="h-4 w-4" /> Filters
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-3" align="start">
        <div className="space-y-3">
          {/* Image types as badges */}
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground mb-2">
              Image types

            </div>
            <div className="flex flex-wrap gap-2">
              {availableTypes.length > 1 && (
                <button
                  type="button"
                  onClick={activateAll}
                  className={`rounded-full text-xs px-2.5 py-1.5 border transition
                    ${allActive ? "bg-primary text-primary-foreground border-primary" : "bg-muted/60 text-muted-foreground border border-input hover:bg-accent hover:text-accent-foreground"}`}
                >
                  All
                </button>
              )}
              {(["thermal", "panoramic", "regular"] as FilterTag[])
                .filter((t) => availableTypes.includes(t))
                .map((tag) => {
                  const active = value.types.includes(tag);
                  // When All is active, show other badges as "passive active" (greyed in)
                  const passiveActive = allActive;
                  return (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => toggleType(tag)}
                      className={`rounded-full capitalize text-xs px-2.5 py-1.5 border transition
                        ${active && !passiveActive ? "bg-primary text-primary-foreground border-primary" : passiveActive ? "bg-muted/60 text-muted-foreground border border-dashed" : "bg-muted text-muted-foreground border border-input hover:bg-accent hover:text-accent-foreground"}`}
                    >
                      {tag}
                    </button>
                  );
                })}
            </div>
          </div>

          {/* Detection classes as badges */}
          <Separator />
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground mb-2">
              Detection classes

            </div>
            <div className="flex flex-wrap gap-2">
              {availableDetectionClasses.map((cls) => {
                const activeDets = value.dets.includes(cls);
                // When All is active, show other badges as "passive active" (greyed in)
                return (
                  <button
                    key={cls}
                    type="button"
                    onClick={() => toggleDetectionClass(cls)}
                    className={`rounded-full capitalize text-xs px-2.5 py-1.5 border transition
                      ${activeDets ? "bg-primary text-primary-foreground border-primary" : "bg-muted text-muted-foreground border border-input hover:bg-accent hover:text-accent-foreground"}`}
                  >
                    {cls}
                  </button>
                );
              })}
            </div>
          </div>

          {availableTypes.includes("thermal") && (
            <>
              <Separator />
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                  <Thermometer className="h-3.5 w-3.5" /> Thermal temperature
                  {availableTypes.includes("thermal") && datasetTempRange && (
                    <span className="ml-auto tabular-nums text-[10px]">{datasetTempRange.min.toFixed(1)}–{datasetTempRange.max.toFixed(1)}°{tempUnit}</span>
                  )}
                </div>

                {/* MinAtLeast */}
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="minAtLeast" className="text-xs whitespace-nowrap w-20">Keep if MAX ≥</Label>
                    <Input
                      id="minAtLeast"
                      type="number"
                      inputMode="decimal"
                      placeholder="inactive"
                      value={minInput}
                      onChange={(e) => setMinInput(e.target.value)}
                      className="h-8 w-26"
                    />
                    <div className="text-sm text-muted-foreground">°{tempUnit}</div>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => {setMinAtLeast(undefined); setMinInput("")}}
                      disabled={minInput === undefined || minInput === ""}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                    <div className="flex-grow" />
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="inline-flex items-center justify-center h-5 w-5 rounded-full border text-[10px] cursor-help"><Info className="h-3.5 w-3.5" /></span>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs text-xs leading-snug">
                        <p>
                          When a value is entered, images are kept if their <span className="font-medium">observed max</span> temperature is ≥ this value. Clear the field or use the button to disable.
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </div>

                {/* MaxAtMost */}
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="maxAtMost" className="text-xs whitespace-nowrap w-20">Keep if MIN ≤</Label>
                    <Input
                      id="maxAtMost"
                      type="number"
                      inputMode="decimal"
                      placeholder="inactive"
                      value={maxInput}
                      onChange={(e) => {
                        setMaxInput(e.target.value);
                      }}
                      className="h-8 w-26"
                    />
                    <div className="text-sm text-muted-foreground">°{tempUnit}</div>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => {setMaxAtMost(undefined); setMaxInput("")}}
                      disabled={maxInput === undefined || maxInput === ""}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                    <div className="flex-grow" />
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="inline-flex items-center justify-center h-5 w-5 rounded-full border text-[10px] cursor-help"><Info className="h-3.5 w-3.5" /></span>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs text-xs leading-snug">
                        <p>
                          When a value is entered, images are kept if their <span className="font-medium">observed min</span> temperature is ≤ this value. Clear the field or use the button to disable.
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </div>
              </div>
              <div className="flex justify-end">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={onReset}
                >
                  Reset Filters
                </Button>
              </div>
            </>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

/**
 * ————————————————————————————————————————————————————————————————
 * GalleryCard — updated to use FiltersPopover + chips
 * ————————————————————————————————————————————————————————————————
 */
interface GalleryCardProps {
  reportId: number;
  //setFilteredImages: (images: ImageBasic[]) => void;
  //filteredImages?: ImageBasic[];
  setSelectedImage: (image: ImageBasic | null) => void;
  detectionFilter: string[];
  setDetectionFilter: (filter: string[]) => void;
  thresholds: { [key: string]: number };
}

export function GalleryCard({
  reportId,
  //setFilteredImages,
  //filteredImages,
  setSelectedImage,
  detectionFilter,
  setDetectionFilter,
  thresholds
}: GalleryCardProps) {
  const { data: images, isLoading } = useImages(reportId);
  const { data: detections } = useDetections(reportId);
  const [search, setSearch] = useState("");
  const apiUrl = getApiUrl();
  const { filteredImages, setFilteredImages } = useFilteredImages();

  const availableTags = useMemo(() => getAvailableTags(images), [images]);
  const availableDetectionClasses = useMemo(() => {
    const classes = new Set<string>();
    for (const detection of detections || []) {
      if (classes.has(detection.class_name)) continue;
      classes.add(detection.class_name);
    }
    return Array.from(classes);
  }, [detections]);
  const datasetTempRange = useMemo(() => getDatasetTempRange(images), [images]);
  const tempUnit = ((): "C" | "F" => {
    // If any thermal image reports a temp unit, surface it (default to C)
    for (const img of images || []) {
      // @ts-ignore
      const td = img.thermal_data as any;
      if (img.thermal && td?.temp_unit && (td.temp_unit === "C" || td.temp_unit === "F")) return td.temp_unit;
    }
    return "C";
  })();

  const [filters, setFilters] = useState<GalleryFilters>({ types: [], temp: {}, dets: detectionFilter });

  useEffect(() => {
    setFilters((prev) => ({ ...prev, dets: detectionFilter }));
  }, [detectionFilter]);

  // Apply filter pipeline whenever deps change
  useEffect(() => {
    console.log("triggered Filtering images");
    const next = filterImages(images, detections, search, filters, thresholds);
    setFilteredImages(next);
  }, [images, detections, search, filters, thresholds, setFilteredImages]);

  const onImageClick = (image: ImageBasic) => setSelectedImage(image);

  const clearSearchAndFilters = () => {
    setSearch("");
    setFilters({ types: [], temp: {}, dets: [] });
    setDetectionFilter([]);
  };

  const hasActiveFilters = filters.types.length > 0 ||
    filters.temp.minAtLeast !== undefined ||
    filters.temp.maxAtMost !== undefined ||
    filters.dets.length > 0;

  return (
    <Card className="min-w-80 min-h-85 max-h-350 flex flex-col px-4 py-3 gap-2">
      <div className="text-lg font-semibold py-2">Images</div>

      {/* Controls */}
      <div className="pb-2 space-y-2">
        <div className="flex flex items-center gap-2">
          {/* Search */}
          <div className="relative sm:w-auto flex-grow min-w-[60px]">
            <Input
              placeholder="search filename"
              value={search}
              onChange={(e) => setSearch(e.target.value)}

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

          {/* Filters popover */}
          <FiltersPopover
            availableTypes={availableTags}
            availableDetectionClasses={availableDetectionClasses}
            value={filters}
            onChange={setFilters}
            datasetTempRange={datasetTempRange}
            tempUnit={tempUnit}
            onReset={clearSearchAndFilters}
          />

          {/* {(hasActiveFilters || search.length > 0) && (
            <Button variant="ghost" onClick={clearSearchAndFilters}>
              Reset
            </Button>
          )} */}
        </div>

        {/* Active filter chips */}
        {(hasActiveFilters || search) && (
          <div className="flex flex-wrap items-center gap-2">
            {search && (
              <Badge variant="secondary" className="px-2 py-1 text-xs">
                Search: “{search}”
                <button className="ml-1" onClick={() => setSearch("")}>
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            )}

            {filters.types.map((t) => (
              <Badge key={t} variant="secondary" className="px-2 py-1 text-xs capitalize">
                {t}
                <button className="ml-1" onClick={() => setFilters({ ...filters, types: filters.types.filter((x) => x !== t) })}>
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}

            {filters.temp.minAtLeast !== undefined && (
              <Badge variant="secondary" className="px-2 py-1 text-xs">
                MAX ≥ {filters.temp.minAtLeast}°{tempUnit}
                <button className="ml-1" onClick={() => setFilters({ ...filters, temp: { ...filters.temp, minAtLeast: undefined } })}>
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            )}

            {filters.temp.maxAtMost !== undefined && (
              <Badge variant="secondary" className="px-2 py-1 text-xs">
                MIN ≤ {filters.temp.maxAtMost}°{tempUnit}
                <button className="ml-1" onClick={() => setFilters({ ...filters, temp: { ...filters.temp, maxAtMost: undefined } })}>
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            )}

            {filters.dets.map((d) => (
              <Badge key={d} variant="secondary" className="px-2 py-1 text-xs">
                Det: {d}
                <button className="ml-1" onClick={() => setFilters({ ...filters, dets: filters.dets.filter((x) => x !== d) })}>
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Gallery Grid */}
      <div className="overflow-auto grow grid grid-cols-[repeat(auto-fit,minmax(110px,1fr))] gap-2 flex-1">
        {isLoading ? (
          <p className="text-md text-muted-foreground">Loading images...</p>
        ) : filteredImages && filteredImages.length > 0 ? (
          filteredImages.map((image) => (
            <Card
              key={"gallery-img-" + image.id}
              className="relative p-0 flex flex-col justify-between items-center h-full gap-0 rounded-sm"
              onClick={() => onImageClick(image)}
            >
            {/* <div className="cursor-pointer" key={"gallery-img-" + image.id} onClick={() => onImageClick(image)}> */}
              <div className="w-full overflow-hidden p-1">
                <img
                  src={`${apiUrl}/${(image as any).thumbnail_url}`}
                  alt={image.filename}
                  className="w-full h-full object-contain rounded-xs"
                  loading="lazy"
                />
              </div>

              <div className="mt-0 w-full p-2 pt-0 pb-1">
                {/* <Tooltip>
                  <TooltipTrigger asChild> */}
                    <p className="text-sm mt-1 w-full truncate text-center"  title={image.filename} >{image.filename}</p>
                  {/* </TooltipTrigger>
                  <TooltipContent>
                    <p>{image.filename}</p>
                  </TooltipContent>
                </Tooltip> */}
              </div>
            </Card> 

          ))
        ) : (
          <p className="text-md text-muted-foreground">No images found</p>
        )}
      </div>
    </Card>
  );
}
