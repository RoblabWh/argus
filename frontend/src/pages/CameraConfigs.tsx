import { useEffect, useState } from "react";
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Copy, Check, Upload, X } from "lucide-react";
import {
  useCameraConfigList,
  useCameraConfig,
  useUpdateCameraConfig,
  useCreateCameraConfig,
} from "@/hooks/cameraConfigHooks";
import { getExifDump } from "@/api";
import type { CameraConfig } from "@/types/cameraConfig";

function emptyConfig(): CameraConfig {
  return {
    _model: "",
    _auto_discovered: false,
    created_at: null,
    width: null,
    height: null,
    projection_type: null,
    gps: { lat: null, lon: null, rel_alt: null, alt: null },
    ir: {
      ir: null,
      ir_value: null,
      ir_image_width: null,
      ir_image_height: null,
      ir_filename_pattern: null,
      ir_scale: null,
    },
    camera_properties: { focal_length: null, fov: null },
    orientation: {
      cam_roll: null,
      cam_yaw: null,
      cam_pitch: null,
      uav_roll: null,
      uav_yaw: null,
      uav_pitch: null,
    },
    fov_correction: null,
    adjust_data: false,
    rgb_orientation_offset: null,
    fallbacks: {},
  };
}

function toStr(v: string | null | undefined): string {
  return v ?? "";
}

function toNullable(v: string): string | null {
  return v.trim() === "" ? null : v;
}

const nullBorder = "border-amber-400 dark:border-amber-500";

function configHasFieldsWithSpaces(config: CameraConfig): boolean {
  const has = (v: string | null) => typeof v === "string" && v.includes(" ");
  return [
    config.width, config.height, config.projection_type,
    config.gps.lat, config.gps.lon, config.gps.rel_alt, config.gps.alt,
    config.ir.ir, config.ir.ir_value, config.ir.ir_image_width,
    config.ir.ir_image_height, config.ir.ir_filename_pattern,
    config.camera_properties.focal_length, config.camera_properties.fov,
    config.orientation.cam_roll, config.orientation.cam_yaw, config.orientation.cam_pitch,
    config.orientation.uav_roll, config.orientation.uav_yaw, config.orientation.uav_pitch,
  ].some(has);
}

function SectionHeading({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2">
      <Separator className="flex-1" />
      <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        {label}
      </span>
      <Separator className="flex-1" />
    </div>
  );
}

// Defined at module level — never re-created on parent renders, preventing input remounting
function StrField({
  label,
  value,
  onChange,
  id,
}: {
  label: string;
  value: string | null;
  onChange: (v: string | null) => void;
  id: string;
}) {
  const hasSpaces = typeof value === "string" && value.includes(" ");
  // use == null to catch both null and undefined (backend may omit keys entirely)
  const borderClass = hasSpaces ? "border-destructive" : value == null ? nullBorder : "";
  return (
    <div>
      <Label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </Label>
      <Input
        id={id}
        value={toStr(value)}
        onChange={(e) => onChange(toNullable(e.target.value))}
        placeholder="null"
        className={`h-8 text-sm font-mono ${borderClass}`}
      />
      {hasSpaces && (
        <p className="text-xs text-destructive mt-0.5">No spaces in key names.</p>
      )}
    </div>
  );
}

export default function CameraConfigs() {
  const { setBreadcrumbs } = useBreadcrumbs();

  // Left panel state
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [newModelName, setNewModelName] = useState("");
  const [formConfig, setFormConfig] = useState<CameraConfig | null>(null);
  const [savedConfig, setSavedConfig] = useState<CameraConfig | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Right panel state
  const [exifDump, setExifDump] = useState<Record<string, unknown> | null>(null);
  const [exifFileName, setExifFileName] = useState<string | null>(null);
  const [exifLoading, setExifLoading] = useState(false);
  const [exifError, setExifError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const { data: configList } = useCameraConfigList();
  const { data: fetchedConfig } = useCameraConfig(selectedModel);
  const updateConfig = useUpdateCameraConfig();
  const createConfig = useCreateCameraConfig();

  useEffect(() => {
    setBreadcrumbs([
      { label: "Settings", href: "/settings" },
      { label: "Camera Configs" },
    ]);
  }, [setBreadcrumbs]);

  useEffect(() => {
    if (fetchedConfig) {
      setFormConfig({ ...fetchedConfig });
      setSavedConfig({ ...fetchedConfig });
    }
  }, [fetchedConfig]);

  function handleSelectChange(value: string) {
    setSaveError(null);
    setSaveSuccess(false);
    if (value === "__new__") {
      setSelectedModel(null);
      setIsNew(true);
      setNewModelName("");
      setFormConfig(emptyConfig());
      setSavedConfig(null);
    } else {
      setSelectedModel(value);
      setIsNew(false);
      setNewModelName("");
      setFormConfig(null);
      setSavedConfig(null);
    }
  }

  function updateField<K extends keyof CameraConfig>(key: K, value: CameraConfig[K]) {
    setFormConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function updateNestedField(
    section: "gps" | "ir" | "camera_properties" | "orientation",
    key: string,
    value: string | number | null
  ) {
    setFormConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        [section]: { ...(prev[section] as Record<string, unknown>), [key]: value },
      };
    });
  }

  function handleReset() {
    if (savedConfig) setFormConfig({ ...savedConfig });
  }

  function formatSaveError(e: unknown, fallback: string, modelName?: string): string {
    const msg = e instanceof Error ? e.message : fallback;
    if (msg.includes("409")) {
      return `A config for "${modelName ?? "this model"}" already exists. Select it from the dropdown to edit it.`;
    }
    return msg;
  }

  async function handleSave() {
    if (!formConfig) return;
    setSaveError(null);
    setSaveSuccess(false);

    if (isNew) {
      const model_name = newModelName.trim();
      if (!model_name) { setSaveError("Model name is required."); return; }
      try {
        const result = await createConfig.mutateAsync({
          model_name,
          initial_data: { ...formConfig, _model: model_name },
        });
        setFormConfig({ ...result });
        setSavedConfig({ ...result });
        setSelectedModel(model_name);
        setIsNew(false);
        setSaveSuccess(true);
      } catch (e) {
        setSaveError(formatSaveError(e, "Save failed.", model_name));
      }
    } else if (selectedModel) {
      try {
        const result = await updateConfig.mutateAsync({ modelName: selectedModel, config: formConfig });
        setFormConfig({ ...result });
        setSavedConfig({ ...result });
        setSaveSuccess(true);
      } catch (e) {
        setSaveError(formatSaveError(e, "Save failed.", selectedModel));
      }
    }
  }

  async function handleCreateFromExif() {
    if (!exifDump) return;

    const exifModel = exifDump["EXIF:Model"] ? String(exifDump["EXIF:Model"]).trim() : "";
    let model_name = newModelName.trim();

    if (!model_name || model_name === exifModel) {
      model_name = exifModel;
    } else if (exifModel) {
      const useManual = window.confirm(
        `The EXIF data identifies this camera as "${exifModel}".\n\nClick OK to create the config under "${model_name}" (your manual entry).\nClick Cancel to switch the name to "${exifModel}" — then click "Create from EXIF" again to confirm.`
      );
      if (!useManual) {
        // Update the field to the EXIF name and let the user confirm by clicking again
        setNewModelName(exifModel);
        setSaveError(`Model name updated to "${exifModel}" from EXIF data. Click "Create from EXIF" again to proceed.`);
        return;
      }
    }

    if (!model_name) {
      setSaveError("No EXIF:Model key found in the dump — enter a model name manually.");
      return;
    }

    setSaveError(null);
    setSaveSuccess(false);
    try {
      const result = await createConfig.mutateAsync({ model_name, exif_dump: exifDump });
      setFormConfig({ ...result });
      setSavedConfig({ ...result });
      setSelectedModel(model_name);
      setIsNew(false);
      setSaveSuccess(true);
      setNewModelName("");
    } catch (e) {
      setSaveError(formatSaveError(e, "Create from EXIF failed.", model_name));
    }
  }

  async function processExifFile(file: File) {
    setExifLoading(true);
    setExifError(null);
    setExifDump(null);
    setExifFileName(file.name);
    try {
      const dump = await getExifDump(file);
      setExifDump(dump);
    } catch (err) {
      setExifError(err instanceof Error ? err.message : "EXIF extraction failed.");
      setExifFileName(null);
    } finally {
      setExifLoading(false);
    }
  }

  function clearExif() {
    setExifDump(null);
    setExifFileName(null);
    setExifError(null);
  }

  async function handleExifFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) await processExifFile(file);
    e.target.value = "";
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave() {
    setIsDragging(false);
  }

  async function handleDropEvent(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) await processExifFile(file);
  }

  async function copyKey(key: string) {
    await navigator.clipboard.writeText(key);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey((prev) => (prev === key ? null : prev)), 1500);
  }

  const isSaving = updateConfig.isPending || createConfig.isPending;
  const fieldsHaveSpaces = formConfig ? configHasFieldsWithSpaces(formConfig) : false;

  return (
    <div className="container mx-auto px-4 pt-4 pb-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Camera Configurations</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-6">
        {/* LEFT: Config Editor */}
        <Card>
          <CardHeader>
            <CardTitle>Config Editor</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Config selector */}
            <div>
              <Label className="text-xs text-muted-foreground">Select Config</Label>
              <Select
                value={isNew ? "__new__" : (selectedModel ?? "")}
                onValueChange={handleSelectChange}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a config…" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__new__">New config…</SelectItem>
                  {configList?.map((c) => (
                    <SelectItem key={c.model_name} value={c.model_name}>
                      {c.model_name}
                      {c.auto_discovered && (
                        <span className="ml-2 text-xs text-muted-foreground">(auto)</span>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Model name — editable only for new configs, spaces stripped on input */}
            {isNew && (
              <div>
                <Label htmlFor="new-model-name" className="text-xs text-muted-foreground">
                  Model Name *
                </Label>
                <Input
                  id="new-model-name"
                  value={newModelName}
                  onChange={(e) => setNewModelName(e.target.value.replace(/\s/g, ""))}
                  placeholder="e.g. DJI_FC3170 (auto-filled from EXIF:Model if left empty)"
                  className="font-mono"
                />
              </div>
            )}

            {formConfig && (
              <>
                {/* Basic */}
                <div className="space-y-3">
                  <SectionHeading label="Basic" />
                  <div className="grid grid-cols-2 gap-3">
                    <StrField
                      label="Width"
                      value={formConfig.width}
                      onChange={(v) => updateField("width", v)}
                      id="f-width"
                    />
                    <StrField
                      label="Height"
                      value={formConfig.height}
                      onChange={(v) => updateField("height", v)}
                      id="f-height"
                    />
                    <StrField
                      label="Projection Type"
                      value={formConfig.projection_type}
                      onChange={(v) => updateField("projection_type", v)}
                      id="f-projection"
                    />
                    <div>
                      <Label htmlFor="f-created-at" className="text-xs text-muted-foreground">
                        Created At
                      </Label>
                      <Input
                        id="f-created-at"
                        value={toStr(formConfig.created_at)}
                        readOnly
                        placeholder="null"
                        className={`h-8 text-sm font-mono ${formConfig.created_at === null ? nullBorder : ""}`}
                      />
                    </div>
                  </div>
                </div>

                {/* GPS */}
                <div className="space-y-3">
                  <SectionHeading label="GPS" />
                  <div className="grid grid-cols-2 gap-3">
                    <StrField label="Latitude key" value={formConfig.gps.lat} onChange={(v) => updateNestedField("gps", "lat", v)} id="g-lat" />
                    <StrField label="Longitude key" value={formConfig.gps.lon} onChange={(v) => updateNestedField("gps", "lon", v)} id="g-lon" />
                    <StrField label="Relative Altitude key" value={formConfig.gps.rel_alt} onChange={(v) => updateNestedField("gps", "rel_alt", v)} id="g-rel-alt" />
                    <StrField label="Altitude key" value={formConfig.gps.alt} onChange={(v) => updateNestedField("gps", "alt", v)} id="g-alt" />
                  </div>
                </div>

                {/* Infrared — 3 cols to reduce scroll */}
                <div className="space-y-3">
                  <SectionHeading label="Infrared" />
                  <div className="grid grid-cols-3 gap-3">
                    <StrField label="IR key" value={formConfig.ir.ir} onChange={(v) => updateNestedField("ir", "ir", v)} id="ir-ir" />
                    <StrField label="IR Value key" value={formConfig.ir.ir_value} onChange={(v) => updateNestedField("ir", "ir_value", v)} id="ir-value" />
                    <StrField label="IR Filename Pattern" value={formConfig.ir.ir_filename_pattern} onChange={(v) => updateNestedField("ir", "ir_filename_pattern", v)} id="ir-pattern" />
                    <StrField label="IR Width key" value={formConfig.ir.ir_image_width} onChange={(v) => updateNestedField("ir", "ir_image_width", v)} id="ir-width" />
                    <StrField label="IR Height key" value={formConfig.ir.ir_image_height} onChange={(v) => updateNestedField("ir", "ir_image_height", v)} id="ir-height" />
                    <div>
                      <Label htmlFor="ir-scale" className="text-xs text-muted-foreground">IR Scale</Label>
                      <Input
                        id="ir-scale"
                        type="number"
                        value={formConfig.ir.ir_scale ?? ""}
                        onChange={(e) =>
                          updateNestedField("ir", "ir_scale", e.target.value === "" ? null : parseFloat(e.target.value))
                        }
                        placeholder="null"
                        className={`h-8 text-sm font-mono ${formConfig.ir.ir_scale === null ? nullBorder : ""}`}
                      />
                    </div>
                  </div>
                </div>

                {/* Camera */}
                <div className="space-y-3">
                  <SectionHeading label="Camera" />
                  <div className="grid grid-cols-2 gap-3">
                    <StrField label="Focal Length key" value={formConfig.camera_properties.focal_length} onChange={(v) => updateNestedField("camera_properties", "focal_length", v)} id="cp-focal" />
                    <StrField label="FOV key" value={formConfig.camera_properties.fov} onChange={(v) => updateNestedField("camera_properties", "fov", v)} id="cp-fov" />
                  </div>
                </div>

                {/* Orientation — 3 cols to reduce scroll */}
                <div className="space-y-3">
                  <SectionHeading label="Orientation" />
                  <div className="grid grid-cols-3 gap-3">
                    <StrField label="Cam Roll key" value={formConfig.orientation.cam_roll} onChange={(v) => updateNestedField("orientation", "cam_roll", v)} id="o-cr" />
                    <StrField label="Cam Yaw key" value={formConfig.orientation.cam_yaw} onChange={(v) => updateNestedField("orientation", "cam_yaw", v)} id="o-cy" />
                    <StrField label="Cam Pitch key" value={formConfig.orientation.cam_pitch} onChange={(v) => updateNestedField("orientation", "cam_pitch", v)} id="o-cp" />
                    <StrField label="UAV Roll key" value={formConfig.orientation.uav_roll} onChange={(v) => updateNestedField("orientation", "uav_roll", v)} id="o-ur" />
                    <StrField label="UAV Yaw key" value={formConfig.orientation.uav_yaw} onChange={(v) => updateNestedField("orientation", "uav_yaw", v)} id="o-uy" />
                    <StrField label="UAV Pitch key" value={formConfig.orientation.uav_pitch} onChange={(v) => updateNestedField("orientation", "uav_pitch", v)} id="o-up" />
                  </div>
                </div>

                {/* Other */}
                <div className="space-y-3">
                  <SectionHeading label="Other" />
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label htmlFor="f-fov-corr" className="text-xs text-muted-foreground">FOV Correction</Label>
                      <Input
                        id="f-fov-corr"
                        type="number"
                        value={formConfig.fov_correction ?? ""}
                        onChange={(e) =>
                          updateField("fov_correction", e.target.value === "" ? null : parseFloat(e.target.value))
                        }
                        placeholder="null"
                        className={`h-8 text-sm font-mono ${formConfig.fov_correction === null ? nullBorder : ""}`}
                      />
                    </div>
                    <div className="flex items-center gap-3 pt-5">
                      <Switch
                        id="f-adjust-data"
                        checked={formConfig.adjust_data}
                        onCheckedChange={(v) => updateField("adjust_data", v)}
                      />
                      <Label htmlFor="f-adjust-data" className="text-xs text-muted-foreground">Adjust Data</Label>
                    </div>
                  </div>
                </div>
              </>
            )}

            {saveError && <p className="text-sm text-destructive">{saveError}</p>}
            {saveSuccess && (
              <p className="text-sm text-green-600 dark:text-green-400">Saved successfully.</p>
            )}
            {fieldsHaveSpaces && (
              <p className="text-sm text-destructive">Some fields contain spaces — fix them before saving.</p>
            )}

            {(isNew || selectedModel) && (
              <div className="flex justify-end gap-2 pt-2">
                {!isNew && (
                  <Button variant="outline" onClick={handleReset} disabled={!savedConfig || isSaving}>
                    Reset
                  </Button>
                )}
                {isNew && exifDump && (
                  <Button variant="outline" onClick={handleCreateFromExif} disabled={isSaving}>
                    Create from EXIF
                  </Button>
                )}
                <Button onClick={handleSave} disabled={isSaving || !formConfig || fieldsHaveSpaces}>
                  {isSaving ? "Saving…" : "Save"}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* RIGHT: EXIF Inspector */}
        <Card>
          <CardHeader>
            <CardTitle>EXIF Inspector</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <label
              htmlFor="exif-file-input"
              className={`flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-xl p-6 cursor-pointer transition-colors text-center
                ${isDragging
                  ? "border-primary bg-primary/5"
                  : "bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700"
                }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDropEvent}
            >
              <Upload className="w-8 h-8 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                {exifLoading ? "Extracting EXIF…" : "Drop or click to upload a sample image"}
              </span>
              <input
                id="exif-file-input"
                type="file"
                accept="image/*"
                className="sr-only"
                onChange={handleExifFileChange}
              />
            </label>

            {exifError && <p className="text-sm text-destructive">{exifError}</p>}

            {exifDump && (
              <div>
                {/* Filename + clear */}
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs text-muted-foreground truncate max-w-[80%]" title={exifFileName ?? ""}>
                    <span className="font-medium">File:</span> {exifFileName}
                    <span className="ml-2">— {Object.keys(exifDump).length} keys found</span>
                  </p>
                  <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0" onClick={clearExif} title="Clear">
                    <X className="h-3 w-3" />
                  </Button>
                </div>

                <div className="rounded-md border overflow-y-auto max-h-[520px]">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-muted z-10">
                      <tr>
                        <th className="w-8" />
                        <th className="text-left px-3 py-2 font-semibold">Key</th>
                        <th className="text-left px-3 py-2 font-semibold">Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(exifDump).map(([key, value]) => (
                        <tr key={key} className="border-t hover:bg-muted/50">
                          <td className="px-2 py-1.5">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6"
                              onClick={() => copyKey(key)}
                              title="Copy key"
                            >
                              {copiedKey === key ? (
                                <Check className="h-3 w-3 text-green-500" />
                              ) : (
                                <Copy className="h-3 w-3" />
                              )}
                            </Button>
                          </td>
                          <td className="px-3 py-1.5 font-mono break-all">{key}</td>
                          <td className="px-3 py-1.5 text-muted-foreground font-mono break-all max-w-[180px] truncate">
                            {String(value)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
