import { useEffect } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { StyleSheet } from 'react-native';
import { useAuth } from '@/hooks/useAuth';
import { requestNotificationPermissions } from '@/services/notificationService';

export default function RootLayout() {
  const { user, loading } = useAuth();
  const router   = useRouter();
  const segments = useSegments();

  useEffect(() => {
    if (loading) return;

    const inAuthGroup = segments[0] === '(auth)';

    if (!user && !inAuthGroup) {
      router.replace('/(auth)/login');
    } else if (user && inAuthGroup) {
      router.replace('/(tabs)');
    }
  }, [user, loading, segments]);

  // Request notification permissions once logged in
  useEffect(() => {
    if (user) requestNotificationPermissions();
  }, [user]);

  return (
    <GestureHandlerRootView style={styles.root}>
      <StatusBar style="auto" />
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(auth)" />
        <Stack.Screen name="(tabs)" />
        <Stack.Screen
          name="plant/[id]"
          options={{ headerShown: true, title: 'Plant Details', presentation: 'card' }}
        />
        <Stack.Screen
          name="plant/add"
          options={{ headerShown: true, title: 'Add Plant', presentation: 'modal' }}
        />
        <Stack.Screen
          name="analyze"
          options={{ headerShown: true, title: 'AI Plant Analysis', presentation: 'modal' }}
        />
      </Stack>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});
