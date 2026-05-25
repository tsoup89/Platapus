/**
 * widgetService.ts
 *
 * Serialises the current plant / task state and pushes it to the iOS
 * home-screen widget via the WidgetBridge native module.
 *
 * Safe to call on Android or in Expo Go — the bridge will be undefined
 * and the function silently no-ops.
 */

import { NativeModules, Platform } from 'react-native';
import { format, startOfDay, isBefore } from 'date-fns';
import type { Plant, CareTask, CareTaskType } from '../types';

const CARE_EMOJIS: Record<CareTaskType, string> = {
  water:     '💧',
  fertilize: '🌿',
  repot:     '🪴',
  trim:      '✂️',
  mist:      '💨',
  custom:    '📋',
};

export interface WidgetTaskItem {
  plantName: string;
  careType:  CareTaskType;
  emoji:     string;
}

export interface WidgetData {
  lastUpdated:    string;   // ISO string
  tasksDueToday:  number;
  tasksOverdue:   number;
  plantsTotal:    number;
  topTasks:       WidgetTaskItem[];  // up to 3 — shown in medium widget
}

export async function syncWidgetData(
  plants:  Plant[],
  tasks:   CareTask[],
): Promise<void> {
  // Only run on real iOS builds (NativeModules.WidgetBridge is undefined in Expo Go)
  const bridge = NativeModules.WidgetBridge;
  if (Platform.OS !== 'ios' || !bridge) return;

  const now     = new Date();
  const todayStart = startOfDay(now);

  const pending = tasks.filter((t) => !t.completed);

  const overdue = pending.filter((t) => isBefore(new Date(t.dueDate), todayStart));
  const dueToday = pending.filter((t) => {
    const due = startOfDay(new Date(t.dueDate));
    return due.getTime() >= todayStart.getTime() &&
           due.getTime() <= todayStart.getTime() + 86_400_000 - 1;
  });

  // Show overdue first, then due today, up to 3 items
  const topItems = [...overdue, ...dueToday].slice(0, 3);

  const data: WidgetData = {
    lastUpdated:   now.toISOString(),
    tasksDueToday: overdue.length + dueToday.length,
    tasksOverdue:  overdue.length,
    plantsTotal:   plants.length,
    topTasks:      topItems.map((t) => ({
      plantName: t.plantName,
      careType:  t.type,
      emoji:     CARE_EMOJIS[t.type] ?? '📋',
    })),
  };

  try {
    await bridge.updateWidgetData(JSON.stringify(data));
  } catch (e) {
    // Non-fatal — widget simply won't update this cycle
    console.warn('[WidgetService] bridge error:', e);
  }
}
