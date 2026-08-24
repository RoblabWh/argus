import { useEffect, useState } from 'react';
import { useBreadcrumbs } from '@/contexts/BreadcrumbContext';
import { ModeToggle } from '@/components/ui/mode-toggle';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Lock,
  Unlock,
  Info,
  Camera,
  Check,
  X,
  Loader2,
  Plus,
  Trash2,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  useSettings,
  useUpdateDetectionColors,
  useUpdateDrzSettings,
  useUpdateWeatherSettings,
  useUpdateWebodmSettings,
  useUpdateHuggingFaceSettings,
  useTestWebodmSettings,
  useTestWeatherSettings,
  useTestDrzSettings,
  useTestHuggingFaceSettings,
} from '@/hooks/settingsHooks';
import { DEFAULT_DETECTION_COLORS } from '@/types/detection';
import type {
  SettingsData,
  SettingsTestResult,
  WebODMSettings,
  OpenWeatherSettings,
  HuggingFaceSettings,
  DRZSettings,
} from '@/types/settings';

function ColorPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (color: string) => void;
}) {
  return (
    <input
      type="color"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-10 w-16 cursor-pointer rounded-md border border-input bg-background"
    />
  );
}

function TestResultChip({
  pending,
  result,
}: {
  pending: boolean;
  result: SettingsTestResult | null;
}) {
  if (pending) {
    return (
      <div className="inline-flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Testing…
      </div>
    );
  }
  if (!result) return null;
  if (result.success) {
    return (
      <div className="inline-flex items-center gap-1.5 rounded-md bg-green-500/10 text-green-700 dark:text-green-400 px-2 py-1 text-sm">
        <Check className="h-4 w-4 shrink-0" />
        <span>{result.message}</span>
        {result.latency_ms != null && (
          <span className="text-muted-foreground">· {result.latency_ms} ms</span>
        )}
      </div>
    );
  }
  return (
    <div className="inline-flex items-center gap-1.5 rounded-md bg-red-500/10 text-red-700 dark:text-red-400 px-2 py-1 text-sm">
      <X className="h-4 w-4 shrink-0" />
      <span>{result.message}</span>
      {result.detail && (
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              aria-label="Show error detail"
              className="ml-0.5 inline-flex items-center hover:opacity-80"
            >
              <Info className="h-3.5 w-3.5" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-96 max-h-80 overflow-auto">
            <div className="text-xs font-mono whitespace-pre-wrap break-words">
              {result.detail}
            </div>
          </PopoverContent>
        </Popover>
      )}
    </div>
  );
}

type ConfirmState = {
  title: string;
  description: string;
  onConfirm: () => void;
} | null;

function ConfirmDialog({
  state,
  onClose,
}: {
  state: ConfirmState;
  onClose: () => void;
}) {
  return (
    <Dialog open={!!state} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{state?.title}</DialogTitle>
          <DialogDescription>{state?.description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              state?.onConfirm();
              onClose();
            }}
          >
            Save anyway
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type LockKey =
  | 'OPEN_WEATHER_API_KEY'
  | 'HF_TOKEN'
  | 'WEBODM_URL'
  | 'WEBODM_USERNAME'
  | 'WEBODM_PASSWORD'
  | 'DRZ_BACKEND_URL'
  | 'DRZ_AUTHOR_NAME'
  | 'DRZ_BACKEND_USERNAME'
  | 'DRZ_BACKEND_PASSWORD';

const INITIAL_LOCKED: Record<LockKey, boolean> = {
  OPEN_WEATHER_API_KEY: true,
  HF_TOKEN: true,
  WEBODM_URL: true,
  WEBODM_USERNAME: true,
  WEBODM_PASSWORD: true,
  DRZ_BACKEND_URL: true,
  DRZ_AUTHOR_NAME: true,
  DRZ_BACKEND_USERNAME: true,
  DRZ_BACKEND_PASSWORD: true,
};

function LockButton({
  locked,
  onToggle,
}: {
  locked: boolean;
  onToggle: () => void;
}) {
  return (
    <Button
      variant="ghost"
      size="icon"
      type="button"
      aria-label={locked ? 'Unlock field' : 'Lock field'}
      onClick={onToggle}
    >
      {locked ? <Lock className="h-5 w-5" /> : <Unlock className="h-5 w-5" />}
    </Button>
  );
}

function LockedField({
  id,
  label,
  type = 'text',
  value,
  onChange,
  locked,
  onToggleLock,
}: {
  id: string;
  label: string;
  type?: 'text' | 'password';
  value: string;
  onChange: (v: string) => void;
  locked: boolean;
  onToggleLock: () => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="flex items-center gap-2">
        <Input
          id={id}
          type={type}
          disabled={locked}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1"
        />
        <LockButton locked={locked} onToggle={onToggleLock} />
      </div>
    </div>
  );
}

const WEBODM_FIELDS = [
  { key: 'WEBODM_URL', label: 'URL', type: 'text' as const },
  { key: 'WEBODM_USERNAME', label: 'Username', type: 'text' as const },
  { key: 'WEBODM_PASSWORD', label: 'Password', type: 'password' as const },
] satisfies Array<{ key: LockKey; label: string; type: 'text' | 'password' }>;

const DRZ_FIELDS = [
  { key: 'DRZ_BACKEND_URL', label: 'Backend URL', type: 'text' as const },
  { key: 'DRZ_AUTHOR_NAME', label: 'Author Name', type: 'text' as const },
  { key: 'DRZ_BACKEND_USERNAME', label: 'Backend Username', type: 'text' as const },
  { key: 'DRZ_BACKEND_PASSWORD', label: 'Backend Password', type: 'password' as const },
] satisfies Array<{ key: LockKey; label: string; type: 'text' | 'password' }>;

export default function Settings() {
  const { setBreadcrumbs } = useBreadcrumbs();
  const { data: settingsData } = useSettings();
  const updateWebodmSettings = useUpdateWebodmSettings();
  const updateWeatherSettings = useUpdateWeatherSettings();
  const updateDrzSettings = useUpdateDrzSettings();
  const updateHuggingFaceSettings = useUpdateHuggingFaceSettings();
  const updateDetectionColors = useUpdateDetectionColors();
  const testWebodm = useTestWebodmSettings();
  const testWeather = useTestWeatherSettings();
  const testDrz = useTestDrzSettings();
  const testHuggingFace = useTestHuggingFaceSettings();

  const [settings, setSettings] = useState<SettingsData>({
    OPEN_WEATHER_API_KEY: '',
    HF_TOKEN: '',
    ENABLE_WEBODM: false,
    WEBODM_URL: '',
    WEBODM_USERNAME: '',
    WEBODM_PASSWORD: '',
    DRZ_BACKEND_URL: '',
    DRZ_AUTHOR_NAME: '',
    DRZ_BACKEND_USERNAME: '',
    DRZ_BACKEND_PASSWORD: '',
    DETECTION_COLORS: { ...DEFAULT_DETECTION_COLORS },
  });

  // Draft row for a class being added — null while the add form is closed.
  const [colorDraft, setColorDraft] = useState<{ name: string; color: string } | null>(null);
  const [colorDraftError, setColorDraftError] = useState<string | null>(null);

  const [locked, setLocked] = useState<Record<LockKey, boolean>>(INITIAL_LOCKED);
  const [weatherResult, setWeatherResult] = useState<SettingsTestResult | null>(null);
  const [hfResult, setHfResult] = useState<SettingsTestResult | null>(null);
  const [webodmResult, setWebodmResult] = useState<SettingsTestResult | null>(null);
  const [drzResult, setDrzResult] = useState<SettingsTestResult | null>(null);
  const [confirmState, setConfirmState] = useState<ConfirmState>(null);

  useEffect(() => {
    setBreadcrumbs([{ label: 'Settings', href: '/settings' }]);
  }, [setBreadcrumbs]);

  useEffect(() => {
    if (settingsData) {
      setSettings({
        OPEN_WEATHER_API_KEY: settingsData.OPEN_WEATHER_API_KEY || '',
        HF_TOKEN: settingsData.HF_TOKEN || '',
        ENABLE_WEBODM: settingsData.ENABLE_WEBODM || false,
        WEBODM_URL: settingsData.WEBODM_URL || '',
        WEBODM_USERNAME: settingsData.WEBODM_USERNAME || '',
        WEBODM_PASSWORD: settingsData.WEBODM_PASSWORD || '',
        DRZ_BACKEND_URL: settingsData.DRZ_BACKEND_URL || '',
        DRZ_AUTHOR_NAME: settingsData.DRZ_AUTHOR_NAME || '',
        DRZ_BACKEND_USERNAME: settingsData.DRZ_BACKEND_USERNAME || '',
        DRZ_BACKEND_PASSWORD: settingsData.DRZ_BACKEND_PASSWORD || '',
        // Whatever the backend has is authoritative, including which classes
        // exist. Only a never-configured backend ({}) falls back to the defaults.
        DETECTION_COLORS: Object.keys(settingsData.DETECTION_COLORS ?? {}).length
          ? { ...settingsData.DETECTION_COLORS }
          : { ...DEFAULT_DETECTION_COLORS },
      });
    }
  }, [settingsData]);

  function handleChange<K extends keyof SettingsData>(key: K, value: SettingsData[K]) {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }

  function toggleLock(key: LockKey) {
    setLocked((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function changeWeather(value: string) {
    handleChange('OPEN_WEATHER_API_KEY', value);
    setWeatherResult(null);
  }

  function changeHuggingFace(value: string) {
    handleChange('HF_TOKEN', value);
    setHfResult(null);
  }

  function changeWebodm<K extends 'ENABLE_WEBODM' | 'WEBODM_URL' | 'WEBODM_USERNAME' | 'WEBODM_PASSWORD'>(
    key: K,
    value: SettingsData[K],
  ) {
    handleChange(key, value);
    setWebodmResult(null);
  }

  function changeDrz<
    K extends 'DRZ_BACKEND_URL' | 'DRZ_AUTHOR_NAME' | 'DRZ_BACKEND_USERNAME' | 'DRZ_BACKEND_PASSWORD',
  >(key: K, value: SettingsData[K]) {
    handleChange(key, value);
    setDrzResult(null);
  }

  async function runTest<T>(
    mutateAsync: (body: T) => Promise<SettingsTestResult>,
    body: T,
  ): Promise<SettingsTestResult> {
    try {
      return await mutateAsync(body);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        success: false,
        message: 'Could not reach test endpoint',
        detail: msg,
        latency_ms: null,
      };
    }
  }

  function saveWithTest<T>(opts: {
    body: T;
    test: (b: T) => Promise<SettingsTestResult>;
    persist: (b: T) => void;
    setResult: (r: SettingsTestResult) => void;
    label: string;
  }) {
    return async () => {
      const result = await runTest(opts.test, opts.body);
      opts.setResult(result);
      if (!result.success) {
        setConfirmState({
          title: `${opts.label} test failed`,
          description: `${result.message}. Save anyway?`,
          onConfirm: () => opts.persist(opts.body),
        });
        return;
      }
      opts.persist(opts.body);
    };
  }

  async function testOpenWeather() {
    const body: OpenWeatherSettings = { OPEN_WEATHER_API_KEY: settings.OPEN_WEATHER_API_KEY };
    setWeatherResult(await runTest(testWeather.mutateAsync, body));
  }
  const saveOpenWeather = saveWithTest({
    body: { OPEN_WEATHER_API_KEY: settings.OPEN_WEATHER_API_KEY } as OpenWeatherSettings,
    test: testWeather.mutateAsync,
    persist: (b) => updateWeatherSettings.mutate(b),
    setResult: setWeatherResult,
    label: 'OpenWeather',
  });

  async function testHuggingFaceToken() {
    const body: HuggingFaceSettings = { HF_TOKEN: settings.HF_TOKEN };
    setHfResult(await runTest(testHuggingFace.mutateAsync, body));
  }
  const saveHuggingFace = saveWithTest({
    body: { HF_TOKEN: settings.HF_TOKEN } as HuggingFaceSettings,
    test: testHuggingFace.mutateAsync,
    persist: (b) => updateHuggingFaceSettings.mutate(b),
    setResult: setHfResult,
    label: 'Hugging Face',
  });

  async function testWebODM() {
    const body: WebODMSettings = {
      ENABLE_WEBODM: settings.ENABLE_WEBODM,
      WEBODM_URL: settings.WEBODM_URL,
      WEBODM_USERNAME: settings.WEBODM_USERNAME,
      WEBODM_PASSWORD: settings.WEBODM_PASSWORD,
    };
    setWebodmResult(await runTest(testWebodm.mutateAsync, body));
  }
  const saveWebODM = saveWithTest({
    body: {
      ENABLE_WEBODM: settings.ENABLE_WEBODM,
      WEBODM_URL: settings.WEBODM_URL,
      WEBODM_USERNAME: settings.WEBODM_USERNAME,
      WEBODM_PASSWORD: settings.WEBODM_PASSWORD,
    } as WebODMSettings,
    test: testWebodm.mutateAsync,
    persist: (b) => updateWebodmSettings.mutate(b),
    setResult: setWebodmResult,
    label: 'WebODM',
  });

  async function testDRZ() {
    const body: DRZSettings = {
      BACKEND_URL: settings.DRZ_BACKEND_URL,
      AUTHOR_NAME: settings.DRZ_AUTHOR_NAME,
      BACKEND_USERNAME: settings.DRZ_BACKEND_USERNAME,
      BACKEND_PASSWORD: settings.DRZ_BACKEND_PASSWORD,
    };
    setDrzResult(await runTest(testDrz.mutateAsync, body));
  }
  const saveDRZ = saveWithTest({
    body: {
      BACKEND_URL: settings.DRZ_BACKEND_URL,
      AUTHOR_NAME: settings.DRZ_AUTHOR_NAME,
      BACKEND_USERNAME: settings.DRZ_BACKEND_USERNAME,
      BACKEND_PASSWORD: settings.DRZ_BACKEND_PASSWORD,
    } as DRZSettings,
    test: testDrz.mutateAsync,
    persist: (b) => updateDrzSettings.mutate(b),
    setResult: setDrzResult,
    label: 'DRZ',
  });

  function setClassColor(className: string, color: string) {
    // Any edit invalidates the "Saved." confirmation next to the button.
    updateDetectionColors.reset();
    setSettings((prev) => ({
      ...prev,
      DETECTION_COLORS: { ...prev.DETECTION_COLORS, [className]: color },
    }));
  }

  function removeClassColor(className: string) {
    updateDetectionColors.reset();
    setSettings((prev) => {
      const next = { ...prev.DETECTION_COLORS };
      delete next[className];
      return { ...prev, DETECTION_COLORS: next };
    });
  }

  function confirmColorDraft() {
    if (!colorDraft) return;
    // class_name is case-sensitive in the DB ("human" and "Person" both exist),
    // so the key must match the detector's output exactly.
    const name = colorDraft.name.trim();
    if (!name) {
      setColorDraftError('Enter a class name.');
      return;
    }
    if (name in settings.DETECTION_COLORS) {
      setColorDraftError(`"${name}" already has a color.`);
      return;
    }
    setClassColor(name, colorDraft.color);
    setColorDraft(null);
    setColorDraftError(null);
  }

  function saveAppearance() {
    updateDetectionColors.mutate({ DETECTION_COLORS: { ...settings.DETECTION_COLORS } });
  }

  return (
    <TooltipProvider>
      <div className="container mx-auto px-4 pt-4 pb-8 space-y-8">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Settings</h1>
          <ModeToggle />
        </div>

        {/* OPEN WEATHER */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Open Weather API
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent className="max-w-sm">
                  Get a free API key at openweathermap.org. Use live weather or
                  historical flight-time data.
                </TooltipContent>
              </Tooltip>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <LockedField
              id="openWeatherApiKey"
              label="API Key"
              value={settings.OPEN_WEATHER_API_KEY}
              onChange={changeWeather}
              locked={locked.OPEN_WEATHER_API_KEY}
              onToggleLock={() => toggleLock('OPEN_WEATHER_API_KEY')}
            />
            <div className="flex items-center justify-end gap-3 flex-wrap">
              <TestResultChip pending={testWeather.isPending} result={weatherResult} />
              <Button
                variant="outline"
                onClick={testOpenWeather}
                disabled={testWeather.isPending}
              >
                {testWeather.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  'Test'
                )}
              </Button>
              <Button onClick={saveOpenWeather} disabled={testWeather.isPending}>
                Save
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* HUGGING FACE (RE-IDENTIFICATION) */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Hugging Face — Object Re-Identification
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent className="max-w-sm">
                  Only needed for object re-identification: the DINOv3 model
                  weights are license-gated. Create a free Hugging Face account,
                  accept the license on the DINOv3 model page, and paste a read
                  access token here. Detection itself works without it.
                </TooltipContent>
              </Tooltip>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <LockedField
              id="hfToken"
              label="Access Token"
              type="password"
              value={settings.HF_TOKEN}
              onChange={changeHuggingFace}
              locked={locked.HF_TOKEN}
              onToggleLock={() => toggleLock('HF_TOKEN')}
            />
            <div className="flex items-center justify-end gap-3 flex-wrap">
              <TestResultChip pending={testHuggingFace.isPending} result={hfResult} />
              <Button
                variant="outline"
                onClick={testHuggingFaceToken}
                disabled={testHuggingFace.isPending}
              >
                {testHuggingFace.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  'Test'
                )}
              </Button>
              <Button onClick={saveHuggingFace} disabled={testHuggingFace.isPending}>
                Save
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* WEB ODM */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              WebODM Settings
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent className="max-w-sm">
                  Requires WebODM Docker container. Set the start script path in
                  .env inside ARGUS directory and restart container.
                </TooltipContent>
              </Tooltip>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <Label htmlFor="enableWebODM">Enable WebODM</Label>
              <Switch
                id="enableWebODM"
                checked={settings.ENABLE_WEBODM}
                onCheckedChange={(v) => changeWebodm('ENABLE_WEBODM', v)}
              />
            </div>

            {WEBODM_FIELDS.map(({ key, label, type }) => (
              <LockedField
                key={key}
                id={key}
                label={label}
                type={type}
                value={settings[key]}
                onChange={(v) => changeWebodm(key, v)}
                locked={locked[key]}
                onToggleLock={() => toggleLock(key)}
              />
            ))}

            <div className="flex items-center justify-end gap-3 flex-wrap">
              <TestResultChip pending={testWebodm.isPending} result={webodmResult} />
              <Button
                variant="outline"
                onClick={testWebODM}
                disabled={testWebodm.isPending}
              >
                {testWebodm.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  'Test'
                )}
              </Button>
              <Button onClick={saveWebODM} disabled={testWebodm.isPending}>
                Save
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* DATA SHARING */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Data Sharing with DRZ Backend
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 text-muted-foreground" />
                </TooltipTrigger>
                <TooltipContent className="max-w-sm">
                  German Rescue Robotics Center integration as part of the
                  E-DRZ project.
                </TooltipContent>
              </Tooltip>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {DRZ_FIELDS.map(({ key, label, type }) => (
              <LockedField
                key={key}
                id={key}
                label={label}
                type={type}
                value={settings[key]}
                onChange={(v) => changeDrz(key, v)}
                locked={locked[key]}
                onToggleLock={() => toggleLock(key)}
              />
            ))}

            <div className="flex items-center justify-end gap-3 flex-wrap">
              <TestResultChip pending={testDrz.isPending} result={drzResult} />
              <Button
                variant="outline"
                onClick={testDRZ}
                disabled={testDrz.isPending}
              >
                {testDrz.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  'Test'
                )}
              </Button>
              <Button onClick={saveDRZ} disabled={testDrz.isPending}>
                Save
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* CAMERA CONFIGS */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Camera className="h-4 w-4" />
              Camera Configurations
            </CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between gap-4">
            <p className="text-sm text-muted-foreground max-w-sm">
              Manage per-model EXIF key mappings used during image metadata extraction.
              Upload a sample image to inspect its metadata keys.
            </p>
            <Button asChild>
              <Link to="/settings/camera_configs">Open</Link>
            </Button>
          </CardContent>
        </Card>

        {/* APPEARANCE */}
        <Card>
          <CardHeader>
            <CardTitle>Appearance — Detection Colors</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Colors are matched against a detection's class name exactly (it is
              case-sensitive). Any class not listed here — including ones you remove —
              gets an automatic color derived from its name.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(settings.DETECTION_COLORS).map(([type, color]) => (
                <div key={type} className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Label className="truncate" title={type}>{type}</Label>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 text-muted-foreground hover:text-destructive"
                          onClick={() => removeClassColor(type)}
                          aria-label={`Remove ${type}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        Remove — <span className="font-mono">{type}</span> then gets an
                        automatic color.
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <ColorPicker value={color} onChange={(c) => setClassColor(type, c)} />
                </div>
              ))}
            </div>

            {colorDraft ? (
              <div className="flex flex-wrap items-end gap-2 rounded-md border border-dashed p-3">
                <div className="space-y-1.5">
                  <Label htmlFor="new-detection-class">Class name</Label>
                  <Input
                    id="new-detection-class"
                    autoFocus
                    className="w-56"
                    placeholder="e.g. land_vehicle"
                    value={colorDraft.name}
                    onChange={(e) => {
                      setColorDraft({ ...colorDraft, name: e.target.value });
                      setColorDraftError(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') confirmColorDraft();
                      if (e.key === 'Escape') {
                        setColorDraft(null);
                        setColorDraftError(null);
                      }
                    }}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Color</Label>
                  <ColorPicker
                    value={colorDraft.color}
                    onChange={(c) => setColorDraft({ ...colorDraft, color: c })}
                  />
                </div>
                <div className="flex items-center gap-1 pb-1">
                  <Button size="sm" onClick={confirmColorDraft}>
                    <Check className="mr-1 h-4 w-4" /> Add
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setColorDraft(null);
                      setColorDraftError(null);
                    }}
                  >
                    <X className="mr-1 h-4 w-4" /> Cancel
                  </Button>
                </div>
                {colorDraftError && (
                  <p className="w-full text-sm text-destructive">{colorDraftError}</p>
                )}
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setColorDraft({ name: '', color: '#ff00ff' })}
              >
                <Plus className="mr-1 h-4 w-4" /> Add class
              </Button>
            )}

            <div className="flex items-center justify-end gap-3">
              {updateDetectionColors.isSuccess && !updateDetectionColors.isPending && (
                <span className="text-sm text-muted-foreground">Saved.</span>
              )}
              {updateDetectionColors.isError && (
                <span className="text-sm text-destructive">
                  {(updateDetectionColors.error as Error).message}
                </span>
              )}
              <Button onClick={saveAppearance} disabled={updateDetectionColors.isPending}>
                {updateDetectionColors.isPending && (
                  <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                )}
                Save
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <ConfirmDialog state={confirmState} onClose={() => setConfirmState(null)} />
    </TooltipProvider>
  );
}
