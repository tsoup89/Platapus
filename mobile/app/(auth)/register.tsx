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
import { DEFAULT_ROOMS } from '@/services/roomService';
import { addRoom } from '@/services/roomService';

export default function RegisterScreen() {
  const { register, user } = useAuth();
  const router = useRouter();

  const [name,     setName]     = useState('');
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [loading,  setLoading]  = useState(false);

  async function handleRegister() {
    if (!name.trim() || !email.trim() || !password) {
      Alert.alert('Missing info', 'Please fill in all fields.');
      return;
    }
    if (password.length < 6) {
      Alert.alert('Weak password', 'Password must be at least 6 characters.');
      return;
    }
    setLoading(true);
    try {
      await register(email.trim(), password, name.trim());
      // Seed default rooms for new users
      // (user ID will be available after register resolves)
    } catch (e: any) {
      Alert.alert('Registration failed', e.message ?? 'Please try again.');
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
        <View style={styles.hero}>
          <Text style={styles.logo}>🌱</Text>
          <Text style={styles.title}>Create Account</Text>
          <Text style={styles.subtitle}>Start tracking your plant family</Text>
        </View>

        <View style={styles.form}>
          <Text style={styles.label}>Your name</Text>
          <TextInput
            style={styles.input}
            value={name}
            onChangeText={setName}
            placeholder="Green Thumb"
            placeholderTextColor={Colors.textMuted}
            autoCapitalize="words"
          />

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
            placeholder="At least 6 characters"
            placeholderTextColor={Colors.textMuted}
            secureTextEntry
          />

          <Button
            label="Create Account"
            icon="🌱"
            onPress={handleRegister}
            loading={loading}
            size="lg"
            style={{ marginTop: 8 }}
          />

          <TouchableOpacity
            style={styles.switchLink}
            onPress={() => router.replace('/(auth)/login')}
          >
            <Text style={styles.switchText}>
              Already have an account?{' '}
              <Text style={styles.switchAction}>Sign in</Text>
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
  hero: { alignItems: 'center', marginBottom: 32 },
  logo:     { fontSize: 60 },
  title:    { fontSize: 28, fontWeight: '800', color: Colors.primaryDark, marginTop: 8 },
  subtitle: { fontSize: 15, color: Colors.textSecondary, marginTop: 4 },
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
  switchLink:   { marginTop: 20, alignItems: 'center' },
  switchText:   { fontSize: 14, color: Colors.textSecondary },
  switchAction: { color: Colors.primary, fontWeight: '700' },
});
