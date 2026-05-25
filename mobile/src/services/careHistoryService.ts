import {
  collection,
  addDoc,
  getDocs,
  query,
  where,
  orderBy,
  limit as fsLimit,
  getDoc,
  doc,
} from 'firebase/firestore';
import { db } from './firebase';
import type { CareTaskType } from '../types';

export interface CareHistoryEntry {
  id: string;
  plantId: string;
  plantName: string;
  plantPhotoUrl?: string;
  userId: string;
  type: CareTaskType;
  date: string;   // ISO date string
  notes?: string;
}

const HISTORY_COL = 'careHistory';

export async function addCareHistoryEntry(
  entry: Omit<CareHistoryEntry, 'id'>,
): Promise<void> {
  await addDoc(collection(db, HISTORY_COL), entry);
}

export async function getPlantHistory(
  plantId: string,
  limitCount = 120,
): Promise<CareHistoryEntry[]> {
  const q = query(
    collection(db, HISTORY_COL),
    where('plantId', '==', plantId),
    orderBy('date', 'desc'),
    fsLimit(limitCount),
  );
  const snap = await getDocs(q);
  return snap.docs.map((d) => ({ id: d.id, ...d.data() } as CareHistoryEntry));
}

export async function getUserHistory(
  userId: string,
  limitCount = 200,
): Promise<CareHistoryEntry[]> {
  const q = query(
    collection(db, HISTORY_COL),
    where('userId', '==', userId),
    orderBy('date', 'desc'),
    fsLimit(limitCount),
  );
  const snap = await getDocs(q);
  return snap.docs.map((d) => ({ id: d.id, ...d.data() } as CareHistoryEntry));
}
