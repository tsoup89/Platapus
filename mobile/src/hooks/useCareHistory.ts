import { useState, useCallback } from 'react';
import {
  getPlantHistory,
  getUserHistory,
  type CareHistoryEntry,
} from '../services/careHistoryService';

export function usePlantHistory(plantId: string | undefined) {
  const [history, setHistory] = useState<CareHistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!plantId) return;
    setLoading(true);
    setError(null);
    try {
      setHistory(await getPlantHistory(plantId));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [plantId]);

  return { history, loading, error, refresh };
}

export function useUserHistory(userId: string | undefined) {
  const [history, setHistory] = useState<CareHistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      setHistory(await getUserHistory(userId));
    } finally {
      setLoading(false);
    }
  }, [userId]);

  return { history, loading, refresh };
}
