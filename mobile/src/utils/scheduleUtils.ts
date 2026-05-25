import type { Plant, CareTask, CareTaskType, CareProfile } from '../types';
import { nextDueDate } from './dateUtils';

interface PendingTask {
  type: CareTaskType;
  dueDate: string;
}

/**
 * Derives all upcoming care tasks from a plant's care profile.
 * These tasks are generated on-the-fly for display and
 * also persisted to Firestore by the care task service.
 */
export function getPendingTasksForPlant(plant: Plant): PendingTask[] {
  const { careProfile } = plant;
  const tasks: PendingTask[] = [];

  tasks.push({
    type: 'water',
    dueDate: nextDueDate(careProfile.lastWatered, careProfile.wateringFrequencyDays),
  });

  if (careProfile.fertilizingFrequencyDays) {
    tasks.push({
      type: 'fertilize',
      dueDate: nextDueDate(careProfile.lastFertilized, careProfile.fertilizingFrequencyDays),
    });
  }

  if (careProfile.repottingFrequencyMonths) {
    tasks.push({
      type: 'repot',
      dueDate: nextDueDate(
        careProfile.lastRepotted,
        careProfile.repottingFrequencyMonths * 30,
      ),
    });
  }

  if (careProfile.trimmingFrequencyDays) {
    tasks.push({
      type: 'trim',
      dueDate: nextDueDate(careProfile.lastTrimmed, careProfile.trimmingFrequencyDays),
    });
  }

  if (careProfile.mistingFrequencyDays) {
    tasks.push({
      type: 'mist',
      dueDate: nextDueDate(careProfile.lastMisted, careProfile.mistingFrequencyDays),
    });
  }

  return tasks;
}

export function careTaskLabel(type: CareTaskType): string {
  const labels: Record<CareTaskType, string> = {
    water: 'Water',
    fertilize: 'Fertilize',
    repot: 'Repot',
    trim: 'Trim',
    mist: 'Mist',
    custom: 'Care',
  };
  return labels[type];
}

export function careTaskEmoji(type: CareTaskType): string {
  const emojis: Record<CareTaskType, string> = {
    water: '💧',
    fertilize: '✨',
    repot: '🪣',
    trim: '✂️',
    mist: '💨',
    custom: '🌱',
  };
  return emojis[type];
}

export function lightLabel(req: CareProfile['lightRequirement']): string {
  return {
    low: 'Low light',
    medium: 'Indirect light',
    high: 'Bright indirect',
    direct: 'Direct sunlight',
  }[req];
}

export function humidityLabel(req: CareProfile['humidityRequirement']): string {
  return { low: 'Low humidity', medium: 'Average humidity', high: 'High humidity' }[req];
}
