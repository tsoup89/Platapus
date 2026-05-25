import {
  collection,
  doc,
  addDoc,
  updateDoc,
  deleteDoc,
  getDocs,
  getDoc,
  query,
  where,
  orderBy,
  serverTimestamp,
} from 'firebase/firestore';
import {
  ref,
  uploadBytes,
  getDownloadURL,
  deleteObject,
} from 'firebase/storage';
import { db, storage } from './firebase';
import type { Plant, CareProfile } from '../types';
import { getPendingTasksForPlant } from '../utils/scheduleUtils';
import { syncCareTasksForPlant } from './careTaskService';
import { addCareHistoryEntry } from './careHistoryService';

const PLANTS_COL = 'plants';

// ─── Photo upload ───────────────────────────────────────────────────────────────

export async function uploadPlantPhoto(
  userId: string,
  plantId: string,
  localUri: string,
): Promise<{ url: string; path: string }> {
  const response = await fetch(localUri);
  const blob = await response.blob();
  const path = `users/${userId}/plants/${plantId}/photo.jpg`;
  const storageRef = ref(storage, path);
  await uploadBytes(storageRef, blob, { contentType: 'image/jpeg' });
  const url = await getDownloadURL(storageRef);
  return { url, path };
}

async function deletePhotoIfExists(photoPath?: string) {
  if (!photoPath) return;
  try { await deleteObject(ref(storage, photoPath)); } catch { /* already gone */ }
}

// ─── CRUD ───────────────────────────────────────────────────────────────────────────────────────

export async function addPlant(
  userId: string,
  data: Omit<Plant, 'id' | 'userId' | 'dateAdded' | 'status'>,
  photoUri?: string,
): Promise<string> {
  const docRef = await addDoc(collection(db, PLANTS_COL), {
    ...data,
    userId,
    status: 'healthy',
    dateAdded: new Date().toISOString(),
    createdAt: serverTimestamp(),
  });

  if (photoUri) {
    const { url, path } = await uploadPlantPhoto(userId, docRef.id, photoUri);
    await updateDoc(docRef, { photoUrl: url, photoPath: path });
  }

  const plant: Plant = {
    ...data,
    id: docRef.id,
    userId,
    status: 'healthy',
    dateAdded: new Date().toISOString(),
  };
  await syncCareTasksForPlant(plant);
  return docRef.id;
}

export async function updatePlant(
  plantId: string,
  updates: Partial<Omit<Plant, 'id' | 'userId'>>,
  newPhotoUri?: string,
): Promise<void> {
  const docRef = doc(db, PLANTS_COL, plantId);
  if (newPhotoUri) {
    const snap = await getDoc(docRef);
    const userId = snap.data()?.userId ?? '';
    const { url, path } = await uploadPlantPhoto(userId, plantId, newPhotoUri);
    updates = { ...updates, photoUrl: url, photoPath: path };
  }
  await updateDoc(docRef, { ...updates, updatedAt: serverTimestamp() });
}

export async function deletePlant(plant: Plant): Promise<void> {
  await deletePhotoIfExists(plant.photoPath);
  await deleteDoc(doc(db, PLANTS_COL, plant.id));
}

export async function getUserPlants(userId: string): Promise<Plant[]> {
  const q = query(
    collection(db, PLANTS_COL),
    where('userId', '==', userId),
    orderBy('dateAdded', 'desc'),
  );
  const snap = await getDocs(q);
  return snap.docs.map((d) => ({ id: d.id, ...d.data() } as Plant));
}

export async function getPlantsByRoom(userId: string, roomId: string): Promise<Plant[]> {
  const q = query(
    collection(db, PLANTS_COL),
    where('userId', '==', userId),
    where('roomId', '==', roomId),
  );
  const snap = await getDocs(q);
  return snap.docs.map((d) => ({ id: d.id, ...d.data() } as Plant));
}

/**
 * Mark a specific care type as done today, update last-done date,
 * resync future tasks, and log to care history.
 */
export async function markCareCompleted(
  plant: Plant,
  careType: 'water' | 'fertilize' | 'repot' | 'trim' | 'mist',
): Promise<void> {
  const fieldMap = {
    water:     'lastWatered',
    fertilize: 'lastFertilized',
    repot:     'lastRepotted',
    trim:      'lastTrimmed',
    mist:      'lastMisted',
  } as const;

  const field = fieldMap[careType];
  const now   = new Date().toISOString();

  await updateDoc(doc(db, PLANTS_COL, plant.id), {
    [`careProfile.${field}`]: now,
    updatedAt: serverTimestamp(),
  });

  // Re-sync the next scheduled task for this plant
  const updated: Plant = {
    ...plant,
    careProfile: { ...plant.careProfile, [field]: now },
  };
  await syncCareTasksForPlant(updated);

  // Log to care history ✓
  await addCareHistoryEntry({
    plantId:      plant.id,
    plantName:    plant.name,
    plantPhotoUrl:plant.photoUrl,
    userId:       plant.userId,
    type:         careType,
    date:         now,
  });
}
