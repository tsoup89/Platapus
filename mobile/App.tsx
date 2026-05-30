import { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { TabNavigator } from './src/navigation/TabNavigator';
import { SetupScreen } from './src/screens/SetupScreen';
import { getBackendUrl } from './src/storage/config';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30_000,
    },
  },
});

export default function App() {
  const [isConfigured, setIsConfigured] = useState<boolean | null>(null);

  useEffect(() => {
    getBackendUrl().then((url) => {
      setIsConfigured(!!url);
    });
  }, []);

  // Still loading from storage — render nothing (keeps native splash visible)
  if (isConfigured === null) return null;

  return (
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider>
        <NavigationContainer>
          {isConfigured ? (
            <TabNavigator />
          ) : (
            <SetupScreen onConfigured={() => setIsConfigured(true)} />
          )}
        </NavigationContainer>
        <StatusBar style="light" />
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}
