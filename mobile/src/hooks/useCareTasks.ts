import { useState, useCallback } from 'react';
import type { CareTask } from '../types';
import { getUserTasks, completeTask, snoozeTask } from '../services/careTaskService';

export function useCareTasks(userId: string | undefined) {
  const [tasks, setTasks]     = useState<CareTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      setTasks(await getUserTasks(userId));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  const complete = useCallback(
    async (taskId: string) => {
      await completeTask(taskId);
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    },
    [],
  );

  const snooze = useCallback(
    async (taskId: string, days: number) => {
      await snoozeTask(taskId, days);
      await refresh();
    },
    [refresh],
  );

  // Derived: tasks due today or overdue
  const todayTasks = tasks.filter((t) => {
    const due = new Date(t.dueDate);
    const now = new Date();
    return due <= now || due.toDateString() === now.toDateString();
  });

  // Upcoming: next 7 days (excluding today)
  const upcomingTasks = tasks.filter((t) => {
    const due = new Date(t.dueDate);
    const now = new Date();
    const in7 = new Date();
    in7.setDate(in7.getDate() + 7);
    return due > now && due <= in7 && due.toDateString() !== now.toDateString();
  });

  return { tasks, todayTasks, upcomingTasks, loading, error, refresh, complete, snooze };
}
