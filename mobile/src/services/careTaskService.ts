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
  writeBatch,
} from 'firebase/firestore';
import { db } from './firebase';
import type { CareTask, CareTaskType, Plant } from '../types';
import { getPendingTasksForPlant } from '../utils/scheduleUtils';

const TASKS_COL = 'careTasks';

/**
 * Re-creates all future (incomplete) care tasks for a plant.
 * Called after adding/editing a plant or after marking care done.
 */
export async function syncCareTasksForPlant(plant: Plant): Promise<void> {
  // Delete existing pending tasks for this plant
  const existingQ = query(
    collection(db, TASKS_COL),
    where('plantId', '==', plant.id),
    where('completed', '==', false),
  );
  const existing = await getDocs(existingQ);
  const batch = writeBatch(db);
  existing.docs.forEach((d) => batch.delete(d.ref));

  // Generate new upcoming tasks from care profile
  const pendingTasks = getPendingTasksForPlant(plant);
  for (const t of pendingTasks) {
    const taskRef = doc(collection(db, TASKS_COL));
    batch.set(taskRef, {
      plantId:      plant.id,
      plantName:    plant.name,
      plantPhotoUrl:plant.photoUrl ?? null,
      userId:       plant.userId,
      type:         t.type,
      dueDate:      t.dueDate,
      completed:    false,
      completedDate:null,
    });
  }

  await batch.commit();
}

export async function getUserTasks(
  userId: string,
  includeCompleted = false,
): Promise<CareTask[]> {
  const constraints = [
    where('userId', '==', userId),
    orderBy('dueDate', 'asc'),
  ] as Parameters<typeof query>[1][];

  if (!includeCompleted) {
    constraints.unshift(where('completed', '==', false));
  }

  const q = query(collection(db, TASKS_COL), ...constraints);
  const snap = await getDocs(q);
  return snap.docs.map((d) => ({ id: d.id, ...d.data() } as CareTask));
}

export async function completeTask(taskId: string): Promise<void> {
  await updateDoc(doc(db, TASKS_COL, taskId), {
    completed:     true,
    completedDate: new Date().toISOString(),
  });
}

export async function snoozeTask(taskId: string, days: number): Promise<void> {
  const newDue = new Date();
  newDue.setDate(newDue.getDate() + days);
  await updateDoc(doc(db, TASKS_COL, taskId), {
    dueDate: newDue.toISOString(),
  });
}
