import {
  format,
  formatDistanceToNow,
  isToday,
  isTomorrow,
  isPast,
  addDays,
  parseISO,
  differenceInDays,
} from 'date-fns';

export function formatDate(iso: string): string {
  const d = parseISO(iso);
  if (isToday(d)) return 'Today';
  if (isTomorrow(d)) return 'Tomorrow';
  return format(d, 'MMM d, yyyy');
}

export function formatRelative(iso: string): string {
  return formatDistanceToNow(parseISO(iso), { addSuffix: true });
}

export function isOverdue(iso: string): boolean {
  return isPast(parseISO(iso)) && !isToday(parseISO(iso));
}

export function isDueToday(iso: string): boolean {
  return isToday(parseISO(iso));
}

export function isDueSoon(iso: string, withinDays = 3): boolean {
  const d = parseISO(iso);
  const diff = differenceInDays(d, new Date());
  return diff >= 0 && diff <= withinDays;
}

export function nextDueDate(lastDoneIso: string | undefined, frequencyDays: number): string {
  const base = lastDoneIso ? parseISO(lastDoneIso) : new Date();
  return addDays(base, frequencyDays).toISOString();
}

export function daysUntil(iso: string): number {
  return differenceInDays(parseISO(iso), new Date());
}

export function todayIso(): string {
  return new Date().toISOString();
}

export function shortDate(iso: string): string {
  return format(parseISO(iso), 'MMM d');
}
