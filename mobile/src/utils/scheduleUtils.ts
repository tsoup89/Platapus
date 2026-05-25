import type { Plant, CareProfile, CareTaskType } from '../types';
import type { Hemisphere } from './seasonUtils';
import { getSeasonalMultiplier } from './seasonUtils';
import { nextDueDate } from './dateUtils';

// Updated by useAuth when the user profile loads so every task sync
// automatically uses the correct hemisphere without prop-drilling.
let _hemisphere: Hemisphere = 'north';
export function setScheduleHemisphere(h: Hemisphere) { _hemisphere = h; }
export function getScheduleHemisphere(): Hemisphere  { return _hemisphere; }

interface PendingTask { type: CareTaskType; dueDate: string; }

/**
 * Derives all upcoming care tasks from a plant’s care profile.
 * Watering frequency is automatically adjusted for the current season.
 */
export function getPendingTasksForPlant(plant: Plant): PendingTask[] {
  const cp    = plant.careProfile;
  const tasks: PendingTask[] = [];

  // Seasonal multiplier only applies to watering — fertilizing/repotting/etc.
  // are driven by explicit schedules and don’t change with seasons.
  const adjWaterDays = Math.max(
    1,
    Math.round(cp.wateringFrequencyDays * getSeasonalMultiplier(_hemisphere)),
  );

  tasks.push({ type: 'water', dueDate: nextDueDate(cp.lastWatered, adjWaterDays) });

  if (cp.fertilizingFrequencyDays)
    tasks.push({ type: 'fertilize', dueDate: nextDueDate(cp.lastFertilized, cp.fertilizingFrequencyDays) });
  if (cp.repottingFrequencyMonths)
    tasks.push({ type: 'repot', dueDate: nextDueDate(cp.lastRepotted, cp.repottingFrequencyMonths * 30) });
  if (cp.trimmingFrequencyDays)
    tasks.push({ type: 'trim', dueDate: nextDueDate(cp.lastTrimmed, cp.trimmingFrequencyDays) });
  if (cp.mistingFrequencyDays)
    tasks.push({ type: 'mist', dueDate: nextDueDate(cp.lastMisted, cp.mistingFrequencyDays) });

  return tasks;
}

export function careTaskLabel(type: CareTaskType): string {
  return { water: 'Water', fertilize: 'Fertilize', repot: 'Repot', trim: 'Trim', mist: 'Mist', custom: 'Care' }[type];
}

export function careTaskEmoji(type: CareTaskType): string {
  return { water: '💧', fertilize: '✨', repot: '🪣', trim: '✂️', mist: '💨', custom: '🌱' }[type];
}

export function lightLabel(req: CareProfile['lightRequirement']): string {
  return { low: 'Low light', medium: 'Indirect light', high: 'Bright indirect', direct: 'Direct sunlight' }[req];
}

export function humidityLabel(req: CareProfile['humidityRequirement']): string {
  return { low: 'Low humidity', medium: 'Average humidity', high: 'High humidity' }[req];
}
