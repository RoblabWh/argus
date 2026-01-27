import { use, useEffect, useState } from 'react';
import { useBreadcrumbs } from '@/contexts/BreadcrumbContext';
import { ModeToggle } from '@/components/ui/mode-toggle';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Lock, Unlock, Info } from 'lucide-react';
import { useSettings, useUpdateDetectionColors, useUpdateDrzSettings, useUpdateWeatherSettings, useUpdateWebodmSettings } from '@/hooks/settingsHooks';
import type { SettingsData } from '@/types/settings';


// Simple color picker wrapper
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



export default function Settings() {
  const { setBreadcrumbs } = useBreadcrumbs();
  const { data: settingsData } = useSettings();
  const updateWebodmSettings = useUpdateWebodmSettings();
  const updateWeatherSettings = useUpdateWeatherSettings();
  const updateDrzSettings = useUpdateDrzSettings();
  const updateDetectionColors = useUpdateDetectionColors();

  const [settings, setSettings] = useState<SettingsData>({
    OPEN_WEATHER_API_KEY: 'dummy_open_weather_key',
    ENABLE_WEBODM: true,
    WEBODM_URL: 'http://localhost:8000',
    WEBODM_USERNAME: 'admin',
    WEBODM_PASSWORD: '******',
    DRZ_BACKEND_URL: 'https://drz.example.org',
    DRZ_AUTHOR_NAME: 'ARGUS',
    DRZ_BACKEND_USERNAME: '',
    DRZ_BACKEND_PASSWORD: '',
    DETECTION_COLORS: {
      fire: '#ff0000',
      vehicle: '#ff0000',
      human: '#000000',
    },
  });

  const [locked, setLocked] = useState({
    WEBODM_URL: true,
    WEBODM_USERNAME: true,
    WEBODM_PASSWORD: true,
  });

  useEffect(() => {
    setBreadcrumbs([{ label: 'Settings', href: '/settings' }]);
  }, [setBreadcrumbs]);

  function handleChange<K extends keyof SettingsData>(key: K, value: SettingsData[K]) {
    setSettings((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function saveOpenWeather() {
    console.log('Save OpenWeather settings:', {
      OPEN_WEATHER_API_KEY: settings.OPEN_WEATHER_API_KEY,
    });
    updateWeatherSettings.mutate({ OPEN_WEATHER_API_KEY: settings.OPEN_WEATHER_API_KEY });
  }

  function saveWebODM() {
    console.log('Save WebODM settings:', {
      ENABLE_WEBODM: settings.ENABLE_WEBODM,
      WEBODM_URL: settings.WEBODM_URL,
      WEBODM_USERNAME: settings.WEBODM_USERNAME,
      WEBODM_PASSWORD: settings.WEBODM_PASSWORD,
    });
    updateWebodmSettings.mutate({
      ENABLE_WEBODM: settings.ENABLE_WEBODM,
      WEBODM_URL: settings.WEBODM_URL,
      WEBODM_USERNAME: settings.WEBODM_USERNAME,
      WEBODM_PASSWORD: settings.WEBODM_PASSWORD,
    });
  }

  function saveDRZ() {
    console.log('Save DRZ settings:', {
      backend_url: settings.DRZ_BACKEND_URL,
      author_name: settings.DRZ_AUTHOR_NAME,
      backend_username: settings.DRZ_BACKEND_USERNAME,
      backend_password: settings.DRZ_BACKEND_PASSWORD,
    });
    updateDrzSettings.mutate({
      BACKEND_URL: settings.DRZ_BACKEND_URL,
      AUTHOR_NAME: settings.DRZ_AUTHOR_NAME,
      BACKEND_USERNAME: settings.DRZ_BACKEND_USERNAME,
      BACKEND_PASSWORD: settings.DRZ_BACKEND_PASSWORD,
    });
  }

  function saveAppearance() {
    console.log('Save Appearance settings:', {
      DETECTION_COLORS: settings.DETECTION_COLORS,
    });
    updateDetectionColors.mutate({ DETECTION_COLORS: { ...settings.DETECTION_COLORS } });
  }

  useEffect(() => {
    if (settingsData) {
      console.log('Loaded settings data:', settingsData);
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

  return (
    <TooltipProvider>
      <div className="container mx-auto px-4 pt-4 space-y-8">
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
            <Label htmlFor="openWeatherApiKey">API Key</Label>
            <Input
              id="openWeatherApiKey"
              value={settings.OPEN_WEATHER_API_KEY}
              onChange={(e) => handleChange('OPEN_WEATHER_API_KEY', e.target.value)}
            />
            <div className='text-right'>
              <Button onClick={saveOpenWeather}>Save OpenWeather Settings</Button>
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
                onCheckedChange={(v) => handleChange('ENABLE_WEBODM', v)}
              />
            </div>

            {(['WEBODM_URL', 'WEBODM_USERNAME', 'WEBODM_PASSWORD'] as const).map((field) => (
              <div key={field} className="flex items-center gap-2">
                <div className="flex-1">
                  <Label htmlFor={field}>{field.replace('WEBODM_', '')}</Label>
                  <Input
                    id={field}
                    type={field === 'WEBODM_PASSWORD' ? 'password' : 'text'}
                    disabled={locked[field]}
                    value={settings[field]}
                    onChange={(e) => handleChange(field, e.target.value)}
                  />
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() =>
                    setLocked((prev) => ({ ...prev, [field]: !prev[field] }))
                  }
                >
                  {locked[field] ? (
                    <Lock className="h-5 w-5" />
                  ) : (
                    <Unlock className="h-5 w-5" />
                  )}
                </Button>
              </div>
            ))}
            <div className='text-right'>
              <Button onClick={saveWebODM}>Save WebODM Settings</Button>
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
            <div>
              <Label htmlFor="drzUrl">DRZ Backend URL</Label>
              <Input
                id="drzUrl"
                value={settings.DRZ_BACKEND_URL}
                onChange={(e) => handleChange('DRZ_BACKEND_URL', e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="authorName">Author Name</Label>
              <Input
                id="authorName"
                value={settings.DRZ_AUTHOR_NAME}
                onChange={(e) => handleChange('DRZ_AUTHOR_NAME', e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="backendUsername">Backend Username</Label>
              <Input
                id="backendUsername"
                value={settings.DRZ_BACKEND_USERNAME}
                onChange={(e) => handleChange('DRZ_BACKEND_USERNAME', e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="backendPassword">Backend Password</Label>
              <Input
                id="backendPassword"
                type="password"
                value={settings.DRZ_BACKEND_PASSWORD}
                onChange={(e) => handleChange('DRZ_BACKEND_PASSWORD', e.target.value)}
              />
            </div>
            <div className='text-right'>
              <Button onClick={saveDRZ}>Save DRZ Settings</Button>
            </div>
          </CardContent>
        </Card>

        {/* APPEARANCE */}
        <Card>
          <CardHeader>
            <CardTitle>Appearance – Detection Colors</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {(['fire', 'vehicle', 'human'] as const).map((type) => (
              <div key={type}>
                <Label>{type}</Label>
                <ColorPicker
                  value={settings.DETECTION_COLORS[type]}
                  onChange={(color) =>
                    setSettings((prev) =>
                      prev
                        ? {
                          ...prev,
                          DETECTION_COLORS: { ...prev.DETECTION_COLORS, [type]: color },
                        }
                        : prev
                    )
                  }
                />
              </div>
            ))}
            <div className="col-span-full">
              <div className='text-right'>
                <Button onClick={saveAppearance}>Save Appearance Settings</Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </TooltipProvider>
  );
}
