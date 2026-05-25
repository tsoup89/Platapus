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
  writeBatch,
} from 'firebase/firestore';
import { db } from './firebase';
import type { CareTask, CareTaskType, Plant } from '../types';
import { getPendingTasksForPlant } from '../utils/scheduleUtils';
import { addCareHistoryEntry } from './careHistoryService';

const TASKS_COL = 'careTasks';

export async function syncCareTasksForPlant(plant: Plant): Promise<void> {
  // Delete all pending (incomplete) tasks for this plant
  const existingQ = query(
    collection(db, TASKS_COL),
    where('plantId', '==', plant.id),
    where('completed', '==', false),
  );
  const existing = await getDocs(existingQ);
  const batch = writeBatch(db);
  existing.docs.forEach((d) => batch.delete(d.ref));

  // Write fresh upcoming tasks derived from the care profile
  for (const t of getPendingTasksForPlant(plant)) {
    const taskRef = doc(collection(db, TASKS_COL));
    batch.set(taskRef, {
      plantId:       plant.id,
      plantName:     plant.name,
      plantPhotoUrl: plant.photoUrl ?? null,
      userId:        plant.userId,
      type:          t.type,
      dueDate:       t.dueDate,
      completed:     false,
      completedDate: null,
    });
  }

  await batch.commit();
}

export async function getUserTasks(
  userId: string,
  includeCompleted = false,
): Promise<CareTask[]> {
  const constraints: Parameters<typeof query>[1][] = [
    where('userId', '==', userId),
    orderBy('dueDate', 'asc'),
  ];
  if (!includeCompleted) constraints.unshift(where('completed', '==', false));

  const snap = await getDocs(query(collection(db, TASKS_COL), ...constraints));
  return snap.docs.map((d) => ({ id: d.id, ...d.data() } as CareTask));
}

/**
 * Mark a task complete and log it to care history automatically.
 */
export async function completeTask(taskId: string): Promise<void> {
  const taskRef  = doc(db, TASKS_COL, taskId);
  const taskSnap = await getDoc(taskRef);
  const now      = new Date().toISOString();

  await updateDoc(taskRef, {
    completed:     true,
    completedDate: now,
  });

  // Write a care history entry so the calendar and timeline pick it up ✓
  if (taskSnap.exists()) {
    const task = { id: taskSnap.id, ...taskSnap.data() } as CareTask;
    await addCareHistoryEntry({
      plantId:       task.plantId,
      plantName:     task.plantName,
      plantPhotoUrl: task.plantPhotoUrl,
      userId:        task.userId,
      type:          task.type,
      date:          now,
    });
  }
}

export async function snoozeTask(taskId: string, days: number): Promise<void> {
  const newDue = new Date();
  newDue.setDate(newDue.getDate() + days);
  await updateDoc(doc(db, TASKS_COL, taskId), {
    dueDate: newDue.toISOString(),
  });
}
