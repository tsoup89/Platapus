/**
 * Weather service using Open-Meteo (free, no API key required)
 * and expo-location for the user's coordinates.
 *
 * Used to intelligently nudge watering schedules:
 *  - Been rainy? Push back watering by 1-2 days.
 *  - Very dry/low humidity? Remind to check soil sooner.
 */

import * as Location from 'expo-location';

export interface WeatherContext {
  recentRainfallMm: number;     // sum of last 3 days
  currentHumidityPct: number;   // max humidity today
  locationName?: string;         // reverse-geocoded city (best-effort)
}

export type WateringNudge = 'delay' | 'check_sooner' | 'none';

export interface WeatherNudge {
  type: WateringNudge;
  message: string;
  emoji: string;
  delayDays: number;  // positive = push back, negative = bring forward
}

export async function getWeatherContext(): Promise<WeatherContext | null> {
  try {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== 'granted') return null;

    const loc = await Location.getCurrentPositionAsync({
      accuracy: Location.Accuracy.Low,
    });
    const { latitude: lat, longitude: lon } = loc.coords;

    // Open-Meteo: past 3 days + today. No API key needed.
    const url = [
      'https://api.open-meteo.com/v1/forecast',
      `?latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}`,
      '&daily=precipitation_sum,relative_humidity_2m_max',
      '&past_days=3&forecast_days=1',
      '&timezone=auto',
    ].join('');

    const resp = await fetch(url);
    if (!resp.ok) return null;
    const data = await resp.json();

    const precipitation: number[] = data.daily?.precipitation_sum  ?? [];
    const humidity:      number[] = data.daily?.relative_humidity_2m_max ?? [];

    // Sum the last 3 days of rain (skip today = last element)
    const recentRainfallMm = precipitation
      .slice(0, 3)
      .reduce((sum, v) => sum + (v ?? 0), 0);

    // Most recent humidity reading
    const currentHumidityPct = humidity[humidity.length - 1] ?? 50;

    // Optionally get city name for the banner
    let locationName: string | undefined;
    try {
      const places = await Location.reverseGeocodeAsync({ latitude: lat, longitude: lon });
      locationName = places[0]?.city ?? places[0]?.region ?? undefined;
    } catch { /* non-critical */ }

    return { recentRainfallMm, currentHumidityPct, locationName };
  } catch {
    return null;
  }
}

export function getWateringNudge(weather: WeatherContext): WeatherNudge {
  const { recentRainfallMm: rain, currentHumidityPct: humidity } = weather;

  if (rain > 15 || humidity > 85) {
    return {
      type:       'delay',
      emoji:      '🌧️',
      message:    `It's been very wet${rain > 15 ? ` (${rain.toFixed(0)}mm rain)` : ''} — your plants probably don\'t need watering yet.`,
      delayDays:  2,
    };
  }
  if (rain > 5 || humidity > 70) {
    return {
      type:       'delay',
      emoji:      '🌦️',
      message:    `Recent rain and high humidity — you can likely delay watering by a day.`,
      delayDays:  1,
    };
  }
  if (rain === 0 && humidity < 35) {
    return {
      type:       'check_sooner',
      emoji:      '☀️',
      message:    `It\'s been hot and dry — check your soil, plants may need water sooner than usual.`,
      delayDays:  -1,
    };
  }
  return { type: 'none', emoji: '', message: '', delayDays: 0 };
}
