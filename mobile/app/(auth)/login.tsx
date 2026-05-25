import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '@/hooks/useAuth';
import { Colors } from '@/constants/Colors';
import { Button } from '@/components/ui/Button';

export default function LoginScreen() {
  const { signIn } = useAuth();
  const router = useRouter();

  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [loading,  setLoading]  = useState(false);

  async function handleLogin() {
    if (!email.trim() || !password) {
      Alert.alert('Missing info', 'Please enter your email and password.');
      return;
    }
    setLoading(true);
    try {
      await signIn(email.trim(), password);
      // Navigation handled by _layout.tsx auth guard
    } catch (e: any) {
      Alert.alert('Sign in failed', e.message ?? 'Please check your credentials.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        {/* Logo / Hero */}
        <View style={styles.hero}>
          <Text style={styles.logo}>🌿</Text>
          <Text style={styles.appName}>Platapus</Text>
          <Text style={styles.tagline}>Keep your plants happy</Text>
        </View>

        {/* Form */}
        <View style={styles.form}>
          <Text style={styles.label}>Email</Text>
          <TextInput
            style={styles.input}
            value={email}
            onChangeText={setEmail}
            placeholder="you@example.com"
            placeholderTextColor={Colors.textMuted}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
          />

          <Text style={styles.label}>Password</Text>
          <TextInput
            style={styles.input}
            value={password}
            onChangeText={setPassword}
            placeholder="••••••••"
            placeholderTextColor={Colors.textMuted}
            secureTextEntry
          />

          <Button
            label="Sign In"
            onPress={handleLogin}
            loading={loading}
            size="lg"
            style={{ marginTop: 8 }}
          />

          <TouchableOpacity
            style={styles.switchLink}
            onPress={() => router.replace('/(auth)/register')}
          >
            <Text style={styles.switchText}>
              Don\'t have an account?{' '}
              <Text style={styles.switchAction}>Create one</Text>
            </Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scroll: { flexGrow: 1, justifyContent: 'center', padding: 24 },
  hero: { alignItems: 'center', marginBottom: 40 },
  logo:    { fontSize: 72 },
  appName: { fontSize: 32, fontWeight: '800', color: Colors.primaryDark, marginTop: 8 },
  tagline: { fontSize: 16, color: Colors.textSecondary, marginTop: 4 },
  form: {
    backgroundColor: Colors.surface,
    borderRadius: 20,
    padding: 24,
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 5,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.textSecondary,
    marginBottom: 6,
    marginTop: 14,
  },
  input: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: Colors.text,
    backgroundColor: Colors.background,
  },
  switchLink:  { marginTop: 20, alignItems: 'center' },
  switchText:  { fontSize: 14, color: Colors.textSecondary },
  switchAction:{ color: Colors.primary, fontWeight: '700' },
});
