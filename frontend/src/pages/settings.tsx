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
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  useSettings,
  useUpdateDetectionColors,
  useUpdateDrzSettings,
  useUpdateWeatherSettings,
  useUpdateWebodmSettings,
  useTestWebodmSettings,
  useTestWeatherSettings,
  useTestDrzSettings,
} from '@/hooks/settingsHooks';
import type {
  SettingsData,
  SettingsTestResult,
  WebODMSettings,
  OpenWeatherSettings,
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
  | 'WEBODM_URL'
  | 'WEBODM_USERNAME'
  | 'WEBODM_PASSWORD'
  | 'DRZ_BACKEND_URL'
  | 'DRZ_AUTHOR_NAME'
  | 'DRZ_BACKEND_USERNAME'
  | 'DRZ_BACKEND_PASSWORD';

const INITIAL_LOCKED: Record<LockKey, boolean> = {
  OPEN_WEATHER_API_KEY: true,
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
  const updateDetectionColors = useUpdateDetectionColors();
  const testWebodm = useTestWebodmSettings();
  const testWeather = useTestWeatherSettings();
  const testDrz = useTestDrzSettings();

  const [settings, setSettings] = useState<SettingsData>({
    OPEN_WEATHER_API_KEY: '',
    ENABLE_WEBODM: false,
    WEBODM_URL: '',
    WEBODM_USERNAME: '',
    WEBODM_PASSWORD: '',
    DRZ_BACKEND_URL: '',
    DRZ_AUTHOR_NAME: '',
    DRZ_BACKEND_USERNAME: '',
    DRZ_BACKEND_PASSWORD: '',
    DETECTION_COLORS: {
      fire: '#ff0000',
      vehicle: '#00ff00',
      human: '#0000ff',
    },
  });

  const [locked, setLocked] = useState<Record<LockKey, boolean>>(INITIAL_LOCKED);
  const [weatherResult, setWeatherResult] = useState<SettingsTestResult | null>(null);
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
        ENABLE_WEBODM: settingsData.ENABLE_WEBODM || false,
        WEBODM_URL: settingsData.WEBODM_URL || '',
        WEBODM_USERNAME: settingsData.WEBODM_USERNAME || '',
        WEBODM_PASSWORD: settingsData.WEBODM_PASSWORD || '',
        DRZ_BACKEND_URL: settingsData.DRZ_BACKEND_URL || '',
        DRZ_AUTHOR_NAME: settingsData.DRZ_AUTHOR_NAME || '',
        DRZ_BACKEND_USERNAME: settingsData.DRZ_BACKEND_USERNAME || '',
        DRZ_BACKEND_PASSWORD: settingsData.DRZ_BACKEND_PASSWORD || '',
        DETECTION_COLORS: {
          fire: settingsData.DETECTION_COLORS.fire || '#ff0000',
          vehicle: settingsData.DETECTION_COLORS.vehicle || '#00ff00',
          human: settingsData.DETECTION_COLORS.human || '#0000ff',
        },
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
              Legacy override for the built-in classes below. New detection classes
              receive a random color automatically.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {(['fire', 'vehicle', 'human'] as const).map((type) => (
                <div key={type} className="space-y-1.5">
                  <Label>{type}</Label>
                  <ColorPicker
                    value={settings.DETECTION_COLORS[type]}
                    onChange={(color) =>
                      setSettings((prev) => ({
                        ...prev,
                        DETECTION_COLORS: { ...prev.DETECTION_COLORS, [type]: color },
                      }))
                    }
                  />
                </div>
              ))}
            </div>
            <div className="flex items-center justify-end">
              <Button onClick={saveAppearance}>Save</Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <ConfirmDialog state={confirmState} onClose={() => setConfirmState(null)} />
    </TooltipProvider>
  );
}
