import React, { useEffect, useMemo, useRef, useState } from "react";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { X, Filter as FilterIcon, Thermometer, Info, Images as ImagesIcon, Boxes, ZoomIn, Pencil, Unlink, Unlink2, Trash, Group } from "lucide-react";
import { toast } from "sonner";
import { getApiUrl } from "@/api";
import type { ImageBasic } from "@/types/image";
import type { Detection } from "@/types/detection";
import { useImages } from "@/hooks/imageHooks";
import { useDetections, useUpdateUniqueObject, useDeleteDetection } from "@/hooks/detectionHooks";
import { useFilteredImages } from "@/contexts/FileteredImagesContext";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { groupDetectionsByObject } from "@/utils/detectionUtils";
import { BBoxCrop } from "@/components/report/mappingReportComponents/slideshow/BBoxCrop";
import { AssignObjectDialog } from "@/components/report/mappingReportComponents/AssignObjectDialog";

/**
 * ————————————————————————————————————————————————————————————————
 * Types
 * ————————————————————————————————————————————————————————————————
 */
export type FilterTag = "thermal" | "panoramic" | "regular";

export type TempFilters = {
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

/** Build a map from image_id to its detections (for efficient lookup) */
function buildDetectionIndex(detections: Detection[] | undefined): Map<number, Detection[]> {
  const index = new Map<number, Detection[]>();
  for (const det of detections || []) {
    const arr = index.get(det.image_id);
    if (arr) arr.push(det);
    else index.set(det.image_id, [det]);
  }
  return index;
}

function filterImages(
  images: ImageBasic[] | undefined,
  search: string,
  filters: GalleryFilters,
  thresholds: Record<string, number> = {},
  detectionIndex: Map<number, Detection[]>, // pre-built index for performance
  restrictIds?: Set<number> | null // hard restriction to these image ids (fire region)
): ImageBasic[] {
  if (!images) return [];

  const term = search.toLowerCase().trim();

  // base search (filename)
  let filtered = term
    ? images.filter((img) => img.filename.toLowerCase().includes(term))
    : images;

  if (restrictIds) {
    filtered = filtered.filter((img) => restrictIds.has(img.id));
  }

  const { types, temp, dets } = filters;

  // Prepare lowercase detection filter names
  const lowerDets = dets.length > 0 ? dets.map((d) => d.toLowerCase().trim()) : [];

  // Case-insensitive threshold lookup
  const thrFor = (cls: string) => {
    const lowerCls = cls.toLowerCase();
    // Find the threshold key that matches (case-insensitive)
    const matchingKey = Object.keys(thresholds).find(
      (key) => key.toLowerCase() === lowerCls
    );
    return matchingKey ? thresholds[matchingKey] : (thresholds["*"] ?? 0.4);
  };

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
      const td = image.thermal_data;
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
    if (lowerDets.length > 0) {
      const imageDets = detectionIndex.get(image.id) ?? [];
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
    const td = img.thermal_data;
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
  selectedObjectId: number | null;
  setSelectedObjectId: (id: number | null) => void;
  highlightedDetectionId: number | null;
  setHighlightedDetectionId: (id: number | null) => void;
  // Overlay region selected on the map (fire/thermal): restrict the grid to its source images
  regionImageIds: number[] | null;
  setRegionImageIds: (ids: number[] | null) => void;
  // Temperature filter — lifted so the map's thermal overlay can follow it
  tempFilter: TempFilters;
  setTempFilter: (t: TempFilters) => void;
}

export function GalleryCard({
  reportId,
  //setFilteredImages,
  //filteredImages,
  setSelectedImage,
  detectionFilter,
  setDetectionFilter,
  thresholds,
  selectedObjectId,
  setSelectedObjectId,
  highlightedDetectionId,
  setHighlightedDetectionId,
  regionImageIds,
  setRegionImageIds,
  tempFilter,
  setTempFilter,
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
  const tempUnit = useMemo((): "C" | "F" => {
    // If any thermal image reports a temp unit, surface it (default to C)
    for (const img of images || []) {
      const td = img.thermal_data;
      if (img.thermal && td?.temp_unit) return td.temp_unit;
    }
    return "C";
  }, [images]);

  // Memoize detection index - only rebuilt when detections change
  const detectionIndex = useMemo(() => buildDetectionIndex(detections), [detections]);

  // ---- Re-identification (objects) view ----
  const [galleryViewMode, setGalleryViewMode] = useState<"images" | "objects">("images");
  const [thumbSize, setThumbSize] = useState(120);
  // The map drives the mode: a selected object forces objects view, an active
  // fire-region filter forces images view (that's where it applies); otherwise
  // honor the toggle.
  const effectiveMode = selectedObjectId != null ? "objects" : regionImageIds ? "images" : galleryViewMode;

  const objectClusters = useMemo(() => groupDetectionsByObject(detections).clusters, [detections]);
  const objectEntries = useMemo(
    () => Array.from(objectClusters.entries()).sort((a, b) => a[0] - b[0]),
    [objectClusters]
  );
  const imageById = useMemo(() => {
    const m = new Map<number, ImageBasic>();
    for (const img of images ?? []) m.set(img.id, img);
    return m;
  }, [images]);
  const hasDetections = (detections?.length ?? 0) > 0;
  const shownMembers = selectedObjectId != null ? (objectClusters.get(selectedObjectId) ?? []) : [];

  const [editDetection, setEditDetection] = useState<Detection | null>(null);
  const updateUniqueObject = useUpdateUniqueObject(reportId);
  const deleteDetectionMut = useDeleteDetection(reportId);

  // Scroll the cross-highlighted crop (from a clicked map marker) into view
  const highlightedCropRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (highlightedDetectionId != null) {
      highlightedCropRef.current?.scrollIntoView({ block: "nearest" });
    }
  }, [highlightedDetectionId]);

  const isBelowThreshold = (det: Detection) => det.score < (thresholds[det.class_name] ?? 0);

  const handleDelete = (det: Detection) => {
    if (!window.confirm(`Permanently delete this ${det.class_name} detection? This cannot be undone.`)) return;
    deleteDetectionMut.mutate(det.id);
    if (highlightedDetectionId === det.id) setHighlightedDetectionId(null);
  };

  const removeFromCluster = (det: Detection) => {
    const prev = det.unique_object_id ?? null;
    updateUniqueObject.mutate({ uniqueObjectId: null, detectionIds: [det.id] });
    toast("Removed from object", {
      action: {
        label: "Undo",
        onClick: () => updateUniqueObject.mutate({ uniqueObjectId: prev, detectionIds: [det.id] }),
      },
    });
  };

  const [filters, setFilters] = useState<GalleryFilters>({ types: [], temp: tempFilter, dets: detectionFilter });

  useEffect(() => {
    setFilters((prev) => ({ ...prev, dets: detectionFilter }));
  }, [detectionFilter]);

  useEffect(() => {
    setFilters((prev) => ({ ...prev, temp: tempFilter }));
  }, [tempFilter]);

  const fireRegionIdSet = useMemo(
    () => (regionImageIds ? new Set(regionImageIds) : null),
    [regionImageIds]
  );

  // Apply filter pipeline whenever deps change
  useEffect(() => {
    const next = filterImages(images, search, filters, thresholds, detectionIndex, fireRegionIdSet);
    setFilteredImages(next);
  }, [images, search, filters, thresholds, detectionIndex, fireRegionIdSet, setFilteredImages]);

  const onImageClick = (image: ImageBasic) => setSelectedImage(image);

  const clearSearchAndFilters = () => {
    setSearch("");
    setFilters({ types: [], temp: {}, dets: [] });
    setDetectionFilter([]);
    setTempFilter({});
    setRegionImageIds(null);
  };

  const hasActiveFilters = filters.types.length > 0 ||
    filters.temp.minAtLeast !== undefined ||
    filters.temp.maxAtMost !== undefined ||
    filters.dets.length > 0 ||
    regionImageIds != null;

  return (
    <Card className="min-w-80 min-h-85 max-h-350 flex flex-col px-4 py-3 gap-2">
      <div className="flex items-center justify-between gap-2 py-2">
        <div className="text-lg font-semibold">{effectiveMode === "objects" ? "Detections" : "Images"}</div>
        {hasDetections && (
          <Tabs
            value={effectiveMode}
            onValueChange={(v) => {
              if (v === "images") {
                setGalleryViewMode("images");
                setSelectedObjectId(null); // also collapse any cluster selected on the map
              } else {
                setGalleryViewMode("objects");
              }
            }}
          >
            <TabsList className="h-8">
              <TabsTrigger value="images" className="gap-1 px-2 py-1 text-xs">
                <ImagesIcon className="h-3.5 w-3.5" /> Images
              </TabsTrigger>
              <TabsTrigger value="objects" className="gap-1 px-2 py-1 text-xs">
                <Group className="h-3.5 w-3.5" /> Objects
              </TabsTrigger>
            </TabsList>
          </Tabs>
        )}
      </div>

      {effectiveMode === "images" ? (
        <>
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
            onChange={(next) => {
              setFilters(next);
              // Sync detection + temperature filter changes to parent (the
              // temp filter also drives the map's thermal overlay)
              setDetectionFilter(next.dets);
              setTempFilter(next.temp);
            }}
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
            {regionImageIds && (
              <Badge variant="secondary" className="px-2 py-1 text-xs">
                Map region ({regionImageIds.length} image{regionImageIds.length === 1 ? "" : "s"})
                <button className="ml-1" onClick={() => setRegionImageIds(null)}>
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            )}

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
                <button className="ml-1" onClick={() => {
                  const temp = { ...filters.temp, minAtLeast: undefined };
                  setFilters({ ...filters, temp });
                  setTempFilter(temp);
                }}>
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            )}

            {filters.temp.maxAtMost !== undefined && (
              <Badge variant="secondary" className="px-2 py-1 text-xs">
                MIN ≤ {filters.temp.maxAtMost}°{tempUnit}
                <button className="ml-1" onClick={() => {
                  const temp = { ...filters.temp, maxAtMost: undefined };
                  setFilters({ ...filters, temp });
                  setTempFilter(temp);
                }}>
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            )}

            {filters.dets.map((d) => {
              const newDets = filters.dets.filter((x) => x !== d);
              return (
                <Badge key={d} variant="secondary" className="px-2 py-1 text-xs">
                  Det: {d}
                  <button className="ml-1" onClick={() => {
                    setFilters({ ...filters, dets: newDets });
                    setDetectionFilter(newDets);
                  }}>
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              );
            })}
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
                  src={`${apiUrl}/${image.thumbnail_url}`}
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
        </>
      ) : (
        /* ———————————————— Objects (detection crops) mode ———————————————— */
        <>
          {/* Object picker + thumbnail zoom (replaces the image search/filter row, no extra height) */}
          <div className="flex items-center gap-2 pb-2">
            <Select
              value={selectedObjectId != null ? String(selectedObjectId) : undefined}
              onValueChange={(v) => setSelectedObjectId(Number(v))}
            >
              <SelectTrigger className="flex-grow min-w-[120px]">
                <SelectValue placeholder={objectEntries.length ? "Select an object" : "No objects"} />
              </SelectTrigger>
              <SelectContent>
                {objectEntries.map(([uid, members]) => (
                  <SelectItem key={uid} value={String(uid)}>
                    Object #{uid} · {members[0].class_name} · {members.length}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="icon"
              title="Deselect object"
              className="shrink-0"
              disabled={selectedObjectId == null}
              onClick={() => setSelectedObjectId(null)}
            >
              <X className="h-4 w-4" />
            </Button>
            <div className="flex items-center gap-1 w-36 shrink-0">
              <ZoomIn className="h-4 w-4 text-muted-foreground" />
              <Slider
                min={60}
                max={220}
                step={10}
                value={[thumbSize]}
                onValueChange={(v) => setThumbSize(v[0])}
              />
            </div>
          </div>

          {/* Crop grid */}
          <div
            className="overflow-auto grow grid gap-2 flex-1 content-start justify-items-center"
            style={{ gridTemplateColumns: `repeat(auto-fill, minmax(${thumbSize}px, 1fr))` }}
          >
            {selectedObjectId == null ? (
              <p className="text-md text-muted-foreground">
                {objectEntries.length
                  ? "Select an object on the map or from the dropdown to view its detections."
                  : "No re-identified objects yet."}
              </p>
            ) : shownMembers.length === 0 ? (
              <p className="text-md text-muted-foreground">No detections for this object.</p>
            ) : (
              [...shownMembers]
                .sort((a, b) => Number(isBelowThreshold(a)) - Number(isBelowThreshold(b)))
                .map((det) => {
                const img = imageById.get(det.image_id);
                if (!img) return null;
                const b = det.bbox as unknown as number[];
                const bbox: [number, number, number, number] = [Number(b[0]), Number(b[1]), Number(b[2]), Number(b[3])];
                const isHighlighted = det.id === highlightedDetectionId;
                const below = isBelowThreshold(det);
                return (
                  <div
                    key={det.id}
                    ref={isHighlighted ? highlightedCropRef : undefined}
                    className="group flex flex-col items-center gap-1"
                    style={{ maxWidth: thumbSize }}
                  >
                    <div
                      className={`relative rounded-sm ${isHighlighted ? "ring-2 ring-primary ring-offset-2" : ""}`}
                      style={{ width: thumbSize, height: thumbSize }}
                    >
                      <BBoxCrop
                        imageUrl={`${apiUrl}/${img.url}`}
                        imageWidth={img.width}
                        imageHeight={img.height}
                        bbox={bbox}
                        thumbSize={thumbSize}
                        alt={img.filename}
                        onClick={() => onImageClick(img)}
                      />
                      {/* Below-threshold: dim + label, but stays clickable (overlay is click-through) */}
                      {below && (
                        <div className="absolute inset-0 bg-black/55 rounded-sm flex items-center justify-center pointer-events-none">
                          <span className="text-[10px] text-white/90 font-medium text-center px-1">below threshold</span>
                        </div>
                      )}
                      {/* Delete whole detection (top-left, separate from the grouping controls) */}
                      <div className="absolute top-1 left-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          type="button"
                          title="Delete detection"
                          className="rounded-sm bg-black/60 hover:bg-red-600 text-white p-1"
                          onClick={(e) => { e.stopPropagation(); handleDelete(det); }}
                        >
                          <Trash className="h-3 w-3" />
                        </button>
                      </div>
                      {/* Hover-reveal edit / remove controls */}
                      <div className="absolute top-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          type="button"
                          title="Change object ID"
                          className="rounded-sm bg-black/60 hover:bg-black/80 text-white p-1"
                          onClick={(e) => { e.stopPropagation(); setEditDetection(det); }}
                        >
                          <Pencil className="h-3 w-3" />
                        </button>
                        <button
                          type="button"
                          title="Remove from object"
                          className="rounded-sm bg-black/60 hover:bg-red-600 text-white p-1"
                          onClick={(e) => { e.stopPropagation(); removeFromCluster(det); }}
                        >
                          <Unlink className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                    <span className="text-[10px] text-muted-foreground truncate w-full text-center" title={img.filename}>
                      {(det.score * 100).toFixed(0)}% · {img.filename}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </>
      )}

      <AssignObjectDialog
        reportId={reportId}
        open={editDetection != null}
        onOpenChange={(o) => { if (!o) setEditDetection(null); }}
        detection={editDetection}
      />
    </Card>
  );
}
