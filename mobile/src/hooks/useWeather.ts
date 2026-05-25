import { useState, useCallback } from 'react';
import {
  getWeatherContext,
  getWateringNudge,
  type WeatherContext,
  type WeatherNudge,
} from '../services/weatherService';

export function useWeather() {
  const [weather, setWeather] = useState<WeatherContext | null>(null);
  const [nudge,   setNudge]   = useState<WeatherNudge | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const ctx = await getWeatherContext();
      setWeather(ctx);
      if (ctx) {
        const n = getWateringNudge(ctx);
        setNudge(n.type !== 'none' ? n : null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  return { weather, nudge, loading, refresh };
}
