import { useState, useCallback } from 'react';
import type { Room } from '../types';
import { getUserRooms, addRoom, updateRoom, deleteRoom } from '../services/roomService';

export function useRooms(userId: string | undefined) {
  const [rooms, setRooms]     = useState<Room[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      setRooms(await getUserRooms(userId));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  const add = useCallback(
    async (name: string, icon: string) => {
      if (!userId) return;
      await addRoom(userId, name, icon);
      await refresh();
    },
    [userId, refresh],
  );

  const edit = useCallback(
    async (roomId: string, updates: Partial<Pick<Room, 'name' | 'icon'>>) => {
      await updateRoom(roomId, updates);
      await refresh();
    },
    [refresh],
  );

  const remove = useCallback(
    async (roomId: string) => {
      await deleteRoom(roomId);
      setRooms((prev) => prev.filter((r) => r.id !== roomId));
    },
    [],
  );

  return { rooms, loading, error, refresh, add, edit, remove };
}
