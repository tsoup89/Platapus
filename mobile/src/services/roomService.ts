import {
  collection,
  doc,
  addDoc,
  updateDoc,
  deleteDoc,
  getDocs,
  query,
  where,
  orderBy,
  serverTimestamp,
} from 'firebase/firestore';
import { db } from './firebase';
import type { Room } from '../types';

const ROOMS_COL = 'rooms';

export async function addRoom(
  userId: string,
  name: string,
  icon: string,
): Promise<string> {
  const docRef = await addDoc(collection(db, ROOMS_COL), {
    userId,
    name,
    icon,
    plantCount: 0,
    createdAt: new Date().toISOString(),
  });
  return docRef.id;
}

export async function updateRoom(
  roomId: string,
  updates: Partial<Pick<Room, 'name' | 'icon'>>,
): Promise<void> {
  await updateDoc(doc(db, ROOMS_COL, roomId), {
    ...updates,
    updatedAt: serverTimestamp(),
  });
}

export async function deleteRoom(roomId: string): Promise<void> {
  await deleteDoc(doc(db, ROOMS_COL, roomId));
}

export async function getUserRooms(userId: string): Promise<Room[]> {
  const q = query(
    collection(db, ROOMS_COL),
    where('userId', '==', userId),
    orderBy('createdAt', 'asc'),
  );
  const snap = await getDocs(q);
  return snap.docs.map((d) => ({ id: d.id, ...d.data() } as Room));
}

export async function incrementRoomPlantCount(
  roomId: string,
  delta: 1 | -1,
): Promise<void> {
  // We do a simple read-modify-write here; for high concurrency use FieldValue.increment
  const snap = await getDocs(
    query(collection(db, ROOMS_COL), where('__name__', '==', roomId)),
  );
  if (snap.empty) return;
  const current = (snap.docs[0].data().plantCount as number) ?? 0;
  await updateDoc(doc(db, ROOMS_COL, roomId), {
    plantCount: Math.max(0, current + delta),
  });
}

export const DEFAULT_ROOMS = [
  { name: 'Living Room', icon: '🛋️' },
  { name: 'Bedroom',     icon: '🛌' },
  { name: 'Kitchen',     icon: '🍳' },
  { name: 'Bathroom',    icon: '🛀' },
  { name: 'Office',      icon: '💼' },
  { name: 'Balcony',     icon: '🌟' },
  { name: 'Greenhouse',  icon: '🌿' },
];
