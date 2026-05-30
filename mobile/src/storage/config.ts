import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'platapicker:backend_url';

export async function getBackendUrl(): Promise<string | null> {
  return AsyncStorage.getItem(KEY);
}

export async function setBackendUrl(ip: string, port: string): Promise<void> {
  await AsyncStorage.setItem(KEY, `http://${ip}:${port}`);
}

export async function clearBackendUrl(): Promise<void> {
  await AsyncStorage.removeItem(KEY);
}
