import { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import axios from 'axios';
import { useQueryClient } from '@tanstack/react-query';
import { getBackendUrl, setBackendUrl, clearBackendUrl } from '../storage/config';

export function SettingsScreen() {
  const [ip, setIp] = useState('');
  const [port, setPort] = useState('8000');
  const [currentUrl, setCurrentUrl] = useState<string | null>(null);
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'ok' | 'error'>('idle');
  const qc = useQueryClient();

  useEffect(() => {
    getBackendUrl().then((url) => {
      setCurrentUrl(url);
      if (url) {
        const parts = url.replace('http://', '').split(':');
        setIp(parts[0] ?? '');
        setPort(parts[1] ?? '8000');
      }
    });
  }, []);

  async function testConnection() {
    setTestStatus('testing');
    try {
      await axios.get(`http://${ip.trim()}:${port.trim()}/api/connection-test`, {
        timeout: 5000,
      });
      setTestStatus('ok');
    } catch {
      setTestStatus('error');
    }
  }

  async function save() {
    await setBackendUrl(ip.trim(), port.trim());
    setCurrentUrl(`http://${ip.trim()}:${port.trim()}`);
    qc.invalidateQueries();
    Alert.alert('Saved', 'Backend URL updated.');
  }

  async function disconnect() {
    Alert.alert('Disconnect', 'Reset to setup screen?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Reset',
        style: 'destructive',
        onPress: async () => {
          await clearBackendUrl();
          qc.clear();
        },
      },
    ]);
  }

  const testLabel =
    testStatus === 'ok'
      ? '✓ Connected'
      : testStatus === 'error'
      ? '✗ Failed'
      : 'Test';

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.heading}>Settings</Text>

        <Text style={styles.section}>Backend Connection</Text>
        {currentUrl ? (
          <Text style={styles.currentUrl}>Current: {currentUrl}</Text>
        ) : null}

        <Text style={styles.label}>IP Address</Text>
        <TextInput
          style={styles.input}
          value={ip}
          onChangeText={(v) => {
            setIp(v);
            setTestStatus('idle');
          }}
          placeholder="192.168.1.100"
          placeholderTextColor="#444"
          keyboardType="numeric"
          autoCapitalize="none"
          autoCorrect={false}
        />

        <Text style={styles.label}>Port</Text>
        <TextInput
          style={styles.input}
          value={port}
          onChangeText={(v) => {
            setPort(v);
            setTestStatus('idle');
          }}
          placeholder="8000"
          placeholderTextColor="#444"
          keyboardType="numeric"
        />

        <View style={styles.row}>
          <TouchableOpacity
            style={[
              styles.btnOutline,
              testStatus === 'ok' && styles.btnOutlineOk,
              testStatus === 'error' && styles.btnOutlineErr,
            ]}
            onPress={testConnection}
            disabled={testStatus === 'testing'}
          >
            {testStatus === 'testing' ? (
              <ActivityIndicator color="#7c3aed" size="small" />
            ) : (
              <Text
                style={[
                  styles.btnOutlineText,
                  testStatus === 'ok' && { color: '#4ade80' },
                  testStatus === 'error' && { color: '#f87171' },
                ]}
              >
                {testLabel}
              </Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity style={styles.btnFill} onPress={save}>
            <Text style={styles.btnFillText}>Save</Text>
          </TouchableOpacity>
        </View>

        <TouchableOpacity style={styles.btnDanger} onPress={disconnect}>
          <Text style={styles.btnDangerText}>Disconnect & Reset</Text>
        </TouchableOpacity>

        <View style={styles.divider} />

        <Text style={styles.section}>About</Text>
        <Text style={styles.about}>Platapicker Mobile v1.0</Text>
        <Text style={styles.about}>Local arbitrage deal tracker</Text>
        <Text style={styles.about}>Connects to your laptop over WiFi or Tailscale</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0d0d1a' },
  container: { padding: 24, paddingBottom: 48 },
  heading: { fontSize: 30, fontWeight: '800', color: '#fff', marginBottom: 28 },
  section: {
    fontSize: 12,
    fontWeight: '700',
    color: '#7c3aed',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 12,
  },
  currentUrl: { fontSize: 12, color: '#4b5563', marginBottom: 16 },
  label: { color: '#9ca3af', fontSize: 13, marginBottom: 6 },
  input: {
    backgroundColor: '#1e1e2e',
    color: '#fff',
    borderRadius: 12,
    padding: 15,
    fontSize: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#2d2d42',
  },
  row: { flexDirection: 'row', gap: 10, marginBottom: 12 },
  btnOutline: {
    flex: 1,
    padding: 14,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: '#7c3aed',
    alignItems: 'center',
  },
  btnOutlineOk: { borderColor: '#4ade80' },
  btnOutlineErr: { borderColor: '#f87171' },
  btnOutlineText: { color: '#7c3aed', fontWeight: '600', fontSize: 14 },
  btnFill: {
    flex: 1,
    padding: 14,
    borderRadius: 12,
    backgroundColor: '#7c3aed',
    alignItems: 'center',
  },
  btnFillText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  btnDanger: {
    padding: 14,
    borderRadius: 12,
    backgroundColor: '#1e1e2e',
    alignItems: 'center',
    marginTop: 4,
  },
  btnDangerText: { color: '#f87171', fontWeight: '600', fontSize: 14 },
  divider: { height: 1, backgroundColor: '#1e1e2e', marginVertical: 28 },
  about: { color: '#374151', fontSize: 13, marginBottom: 5 },
});
