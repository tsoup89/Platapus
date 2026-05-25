import { useState, useCallback } from 'react';
import type { Plant } from '../types';
import { getUserPlants, addPlant, updatePlant, deletePlant, markCareCompleted } from '../services/plantService';

export function usePlants(userId: string | undefined) {
  const [plants, setPlants]   = useState<Plant[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getUserPlants(userId);
      setPlants(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  const add = useCallback(
    async (
      data: Omit<Plant, 'id' | 'userId' | 'dateAdded' | 'status'>,
      photoUri?: string,
    ) => {
      if (!userId) return;
      await addPlant(userId, data, photoUri);
      await refresh();
    },
    [userId, refresh],
  );

  const edit = useCallback(
    async (plantId: string, updates: Partial<Omit<Plant, 'id' | 'userId'>>, newPhotoUri?: string) => {
      await updatePlant(plantId, updates, newPhotoUri);
      await refresh();
    },
    [refresh],
  );

  const remove = useCallback(
    async (plant: Plant) => {
      await deletePlant(plant);
      setPlants((prev) => prev.filter((p) => p.id !== plant.id));
    },
    [],
  );

  const markDone = useCallback(
    async (plant: Plant, type: Parameters<typeof markCareCompleted>[1]) => {
      await markCareCompleted(plant, type);
      await refresh();
    },
    [refresh],
  );

  return { plants, loading, error, refresh, add, edit, remove, markDone };
}
