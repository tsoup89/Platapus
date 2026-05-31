import { useEffect, useRef } from 'react';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import client from '../api/client';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerForPushNotificationsAsync(): Promise<string | null> {
  if (!Device.isDevice) return null;

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('deals', {
      name: 'Deal Alerts',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
    });
  }

  const { status: existing } = await Notifications.getPermissionsAsync();
  const { status } =
    existing !== 'granted'
      ? await Notifications.requestPermissionsAsync()
      : { status: existing };

  if (status !== 'granted') return null;

  // Note: for production EAS builds, pass projectId from app.json extra.eas.projectId
  const { data: token } = await Notifications.getExpoPushTokenAsync();
  return token;
}

export function usePushNotifications() {
  const notifListener = useRef<Notifications.Subscription>();
  const responseListener = useRef<Notifications.Subscription>();

  useEffect(() => {
    registerForPushNotificationsAsync().then(async (token) => {
      if (!token) return;
      try {
        await client.post('/push-token', { token });
      } catch {
        // non-fatal — app works without push
      }
    });

    notifListener.current = Notifications.addNotificationReceivedListener(() => {
      // foreground notification received
    });

    responseListener.current = Notifications.addNotificationResponseReceivedListener(
      (response) => {
        const { listing_id } = response.notification.request.content.data as {
          listing_id?: number;
        };
        if (listing_id) {
          // Future: navigate to listing detail
          console.log('Tapped deal push for listing', listing_id);
        }
      }
    );

    return () => {
      notifListener.current?.remove();
      responseListener.current?.remove();
    };
  }, []);
}
