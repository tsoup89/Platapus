import { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import axios from 'axios';
import { setBackendUrl } from '../storage/config';

interface Props {
  onConfigured: () => void;
}

export function SetupScreen({ onConfigured }: Props) {
  const [ip, setIp] = useState('192.168.');
  const [port, setPort] = useState('8000');
  const [status, setStatus] = useState<'idle' | 'testing' | 'ok' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  async function handleConnect() {
    const trimIp = ip.trim();
    const trimPort = port.trim();
    if (!trimIp || !trimPort) return;

    setStatus('testing');
    setErrorMsg('');

    const url = `http://${trimIp}:${trimPort}`;
    try {
      await axios.get(`${url}/api/connection-test`, { timeout: 5000 });
      await setBackendUrl(trimIp, trimPort);
      setStatus('ok');
      setTimeout(onConfigured, 500);
    } catch (e: any) {
      setStatus('error');
      setErrorMsg(e?.message ?? 'Could not reach backend');
    }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={styles.container}
          keyboardShouldPersistTaps="handled"
        >
          <Text style={styles.logo}>🦆</Text>
          <Text style={styles.title}>Platapicker</Text>
          <Text style={styles.subtitle}>
            Enter your laptop’s local IP to connect over WiFi
          </Text>

          <Text style={styles.label}>IP Address</Text>
          <TextInput
            style={styles.input}
            value={ip}
            onChangeText={setIp}
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
            onChangeText={setPort}
            placeholder="8000"
            placeholderTextColor="#444"
            keyboardType="numeric"
          />

          {status === 'error' && (
            <Text style={styles.errorText}>{errorMsg}</Text>
          )}
          {status === 'ok' && (
            <Text style={styles.successText}>Connected!</Text>
          )}

          <TouchableOpacity
            style={[styles.btn, status === 'testing' && styles.btnBusy]}
            onPress={handleConnect}
            disabled={status === 'testing'}
          >
            {status === 'testing' ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.btnText}>Connect</Text>
            )}
          </TouchableOpacity>

          <Text style={styles.hint}>
            Make sure Platapicker is running on your laptop{`\n`}(npm run dev) and
            both devices are on the same WiFi.{`\n\n`}Using Tailscale? Enter your
            laptop’s Tailscale IP instead.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0d0d1a' },
  flex: { flex: 1 },
  container: { flexGrow: 1, justifyContent: 'center', padding: 28 },
  logo: { fontSize: 72, textAlign: 'center', marginBottom: 8 },
  title: {
    fontSize: 34,
    fontWeight: '800',
    color: '#fff',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 15,
    color: '#6b7280',
    textAlign: 'center',
    marginBottom: 36,
    lineHeight: 22,
  },
  label: { color: '#9ca3af', fontSize: 13, marginBottom: 6 },
  input: {
    backgroundColor: '#1e1e2e',
    color: '#fff',
    borderRadius: 12,
    padding: 15,
    fontSize: 17,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#2d2d42',
  },
  errorText: {
    color: '#f87171',
    fontSize: 13,
    textAlign: 'center',
    marginBottom: 10,
  },
  successText: {
    color: '#4ade80',
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
    marginBottom: 10,
  },
  btn: {
    backgroundColor: '#7c3aed',
    borderRadius: 14,
    padding: 17,
    alignItems: 'center',
    marginTop: 4,
    marginBottom: 28,
  },
  btnBusy: { opacity: 0.6 },
  btnText: { color: '#fff', fontSize: 17, fontWeight: '700' },
  hint: {
    color: '#374151',
    fontSize: 13,
    textAlign: 'center',
    lineHeight: 20,
  },
});
