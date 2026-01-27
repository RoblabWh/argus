import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import {
  RotateCcw,
  Droplets,
  Wind,
  Eye,
  CloudLightning,
  CloudDrizzle,
  CloudRain,
  Snowflake,
  CloudFog,
  Sun,
  CloudSun,
  Cloud,
  Thermometer,
  Gauge,
  ArrowDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Weather } from "@/types/weather";

// Map open_weather_id ranges to Lucide icons or fallback
const getWeatherIcon = (id: number) => {
  if (id >= 200 && id < 300) return CloudLightning; // Thunderstorm
  if (id >= 300 && id < 500) return CloudDrizzle;   // Drizzle
  if (id >= 500 && id < 600) return CloudRain;      // Rain
  if (id >= 600 && id < 700) return Snowflake;      // Snow
  if (id >= 700 && id < 800) return CloudFog;       // Atmosphere (mist, fog, etc.)
  if (id === 800) return Sun;                       // Clear
  if (id === 801) return CloudSun;                  // Few clouds
  if (id > 801 && id < 900) return Cloud;           // Cloudy
  return Thermometer;                               // Fallback
};

const getWindDirectionLabel = (deg: number) => {
  const directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return directions[Math.round(deg / 45) % 8];
};

type Props = {
  data: Weather | undefined;
  onReload: () => void;
};

export function WeatherCard({ data, onReload }: Props) {
  if (!data || Object.keys(data).length === 0) {
    data = {} as Weather; // Fallback to empty object if no data
  }

  const {
    temperature = "?",
    description = "No Weather Data",
    humidity = "?",
    wind_speed = "?",
    wind_dir_deg = 0,
    visibility = "?",
    pressure = "?",
    open_weather_id = 0,
    timestamp = null,
  } = data;

  //round temperature to 1 decimal place if it's a number
  const temperatureValue = typeof temperature === "number" ? Math.round(temperature * 10) / 10 : temperature;
  const visibilityValue = typeof visibility === "number" ? Math.round(visibility / 1000 * 10) / 10 : visibility;
  const lastUpdated = timestamp ? "From " + new Date(timestamp).toLocaleString() : "Loading weather data failed";
  // const timeAgo = new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(
  //   -Math.round((Date.now() - lastUpdated.getTime()) / 60000),
  //   "minutes"
  // );

  const WeatherIcon = getWeatherIcon(Number(open_weather_id));
  const windDirLabel = getWindDirectionLabel(wind_dir_deg);

  return (
    <Card className="min-w-52 max-w-114 flex-1 relative overflow-hidden pb-3">
      {/* Background Icon */}
      <WeatherIcon className="absolute right-2 top-1 w-24 h-24 opacity-100 text-muted-foreground dark:text-white z-0 pointer-events-none" />

      {/* Gradient Fade Overlay */}
      {/* <div className="absolute inset-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/60 to-white/0 dark:from-gray-900/100 dark:via-gray-900/70 dark:to-gray-900/0" /> */}
      <div className="absolute w-40 h-30 right-0 top-0 z-10 pointer-events-none bg-gradient-to-l from-white/90 via-white/75 to-white/55 dark:from-gray-900/100 dark:via-gray-900/85 dark:to-gray-900/60" />

      <CardContent className="px-4 pt-1 flex flex-col items-start space-y-1 relative z-10">
        {/* Top Row: Temp & Reload */}
        <div className="flex justify-between items-start w-full">
          <div className="text-xl font-bold leading-none">{temperatureValue}°C</div>

        </div>

        {/* Description */}
        <div className="text-xs capitalize text-muted-foreground">{description}</div>

        {/* Wind Direction */}
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex items-center gap-0 text-xs mt-1">
              <Wind className="w-3 h-3 mr-1" />
              {wind_speed} m/s
              <ArrowDown
                className="w-3 h-3 ml-1"
                style={{ transform: `rotate(${wind_dir_deg}deg)` }}
              />
              ({windDirLabel})
            </div>
          </TooltipTrigger>
          <TooltipContent>
            <p>Wind from {windDirLabel} ({wind_dir_deg}°)</p>
          </TooltipContent>
        </Tooltip>

        {/* Tooltip Row with Details */}
        <div className="flex gap-2 mt-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Droplets className="w-3 h-3" />
                {humidity}%
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <p>Humidity</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Eye className="w-3 h-3" />
                {visibilityValue} km
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <p>Visibility</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Gauge className="w-3 h-3" />
                {pressure} hPa
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <p>Pressure</p>
            </TooltipContent>
          </Tooltip>
        </div>

        {/* Footer */}
        <div className="w-full text-right mt-0 flex justify-end items-center text-xs text-muted-foreground">
          <span className="text-[10px] text-muted-foreground">{lastUpdated}</span>
          {/* <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                className="w-6 h-6 rounded-full text-muted-foreground"
                variant="outline"
                onClick={onReload}
              >
                <RotateCcw className="w-3 h-3" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Reload</p>
            </TooltipContent>
          </Tooltip> */}
        </div>
      </CardContent>
    </Card>
  );
}