import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import type { CareTask, NotificationPreferences } from '../types';
import { formatDate, daysUntil } from '../utils/dateUtils';
import { careTaskLabel, careTaskEmoji } from '../utils/scheduleUtils';

// Configure how notifications are shown while app is in foreground
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge:  true,
  }),
});

export async function requestNotificationPermissions(): Promise<boolean> {
  if (!Device.isDevice) {
    console.warn('Push notifications only work on a real device.');
    return false;
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') return false;

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('plant-care', {
      name: 'Plant Care Reminders',
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      lightColor:       '#2d7a47',
    });
  }

  return true;
}

export async function getExpoPushToken(): Promise<string | null> {
  try {
    const token = await Notifications.getExpoPushTokenAsync();
    return token.data;
  } catch {
    return null;
  }
}

/**
 * Schedule a local notification for a care task.
 * Returns the notification identifier for later cancellation.
 */
export async function scheduleTaskNotification(
  task: CareTask,
  prefs: NotificationPreferences,
): Promise<string | null> {
  if (!prefs.enabled) return null;

  const dueDate = new Date(task.dueDate);
  // Notify at the user's preferred time on the due day
  const trigger = new Date(dueDate);
  trigger.setHours(prefs.dailyReminderHour, prefs.dailyReminderMinute, 0, 0);

  // If the trigger is in the past, skip
  if (trigger.getTime() < Date.now()) return null;

  const emoji = careTaskEmoji(task.type);
  const label = careTaskLabel(task.type);

  const id = await Notifications.scheduleNotificationAsync({
    content: {
      title: `${emoji} Time to ${label.toLowerCase()} your plant!`,
      body:  `${task.plantName} needs ${label.toLowerCase()}ing today.`,
      data:  { taskId: task.id, plantId: task.plantId },
      sound: true,
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.DATE,
      date: trigger,
    },
  });

  return id;
}

export async function cancelAllNotifications(): Promise<void> {
  await Notifications.cancelAllScheduledNotificationsAsync();
}

export async function scheduleAllTaskNotifications(
  tasks: CareTask[],
  prefs: NotificationPreferences,
): Promise<void> {
  await cancelAllNotifications();
  for (const task of tasks) {
    if (!task.completed) {
      await scheduleTaskNotification(task, prefs);
    }
  }
}
