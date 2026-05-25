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
  Timestamp,
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

const PLANTS_COL = 'plants';

// ─── Photo upload ────────────────────────────────────────────────────────────────────────

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
  try {
    await deleteObject(ref(storage, photoPath));
  } catch {
    // Photo may already be deleted; safe to ignore
  }
}

// ─── CRUD ────────────────────────────────────────────────────────────────────────────────────────

export async function addPlant(
  userId: string,
  data: Omit<Plant, 'id' | 'userId' | 'dateAdded' | 'status'>,
  photoUri?: string,
): Promise<string> {
  // Create the plant document first to get its ID
  const docRef = await addDoc(collection(db, PLANTS_COL), {
    ...data,
    userId,
    status: 'healthy',
    dateAdded: new Date().toISOString(),
    createdAt: serverTimestamp(),
  });

  // Upload photo if provided
  if (photoUri) {
    const { url, path } = await uploadPlantPhoto(userId, docRef.id, photoUri);
    await updateDoc(docRef, { photoUrl: url, photoPath: path });
  }

  // Sync care tasks into Firestore
  const plant = { ...data, id: docRef.id, userId, status: 'healthy' as const, dateAdded: new Date().toISOString() };
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
    // Delete old photo if exists
    const userId = updates.userId ?? '';
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

export async function markCareCompleted(
  plant: Plant,
  careType: 'water' | 'fertilize' | 'repot' | 'trim' | 'mist',
): Promise<void> {
  const fieldMap: Record<string, keyof Pick<CareProfile,
    'lastWatered' | 'lastFertilized' | 'lastRepotted' | 'lastTrimmed' | 'lastMisted'>> = {
    water:     'lastWatered',
    fertilize: 'lastFertilized',
    repot:     'lastRepotted',
    trim:      'lastTrimmed',
    mist:      'lastMisted',
  };
  const field = fieldMap[careType];
  const now = new Date().toISOString();

  await updateDoc(doc(db, PLANTS_COL, plant.id), {
    [`careProfile.${field}`]: now,
    updatedAt: serverTimestamp(),
  });

  // Re-sync future task
  const updated: Plant = {
    ...plant,
    careProfile: { ...plant.careProfile, [field]: now },
  };
  await syncCareTasksForPlant(updated);
}
