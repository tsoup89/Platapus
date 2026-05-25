import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Switch,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/hooks/useAuth';
import { Colors } from '@/constants/Colors';
import { cancelAllNotifications } from '@/services/notificationService';

export default function SettingsScreen() {
  const { profile, signOut, updateNotificationPrefs } = useAuth();
  const prefs = profile?.notificationPreferences;

  const [notificationsOn, setNotificationsOn] = useState(prefs?.enabled ?? true);

  async function toggleNotifications(value: boolean) {
    setNotificationsOn(value);
    if (!value) await cancelAllNotifications();
    await updateNotificationPrefs({ ...prefs!, enabled: value });
  }

  function handleSignOut() {
    Alert.alert(
      'Sign out',
      'Are you sure you want to sign out?',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Sign Out', style: 'destructive', onPress: signOut },
      ],
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        <Text style={styles.title}>Settings ⚙️</Text>

        {/* Profile */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Account</Text>
          <View style={styles.row}>
            <Text style={styles.rowLabel}>Name</Text>
            <Text style={styles.rowValue}>{profile?.displayName ?? '—'}</Text>
          </View>
          <View style={[styles.row, styles.rowLast]}>
            <Text style={styles.rowLabel}>Email</Text>
            <Text style={styles.rowValue}>{profile?.email ?? '—'}</Text>
          </View>
        </View>

        {/* Notifications */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Notifications</Text>
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowLabel}>Care Reminders</Text>
              <Text style={styles.rowSub}>Get notified when it\'s time to water, fertilize, etc.</Text>
            </View>
            <Switch
              value={notificationsOn}
              onValueChange={toggleNotifications}
              trackColor={{ false: Colors.border, true: Colors.primaryLight }}
              thumbColor={notificationsOn ? Colors.primary : '#f4f4f4'}
            />
          </View>
          <View style={[styles.row, styles.rowLast]}>
            <Text style={styles.rowLabel}>Reminder time</Text>
            <Text style={styles.rowValue}>
              {`${String(prefs?.dailyReminderHour ?? 8).padStart(2, '0')}:${String(prefs?.dailyReminderMinute ?? 0).padStart(2, '0')}`}
            </Text>
          </View>
        </View>

        {/* About */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>About</Text>
          <View style={styles.row}>
            <Text style={styles.rowLabel}>App</Text>
            <Text style={styles.rowValue}>Gamgee v1.0</Text>
          </View>
          <View style={[styles.row, styles.rowLast]}>
            <Text style={styles.rowLabel}>AI powered by</Text>
            <Text style={styles.rowValue}>Claude (Anthropic) 🤖</Text>
          </View>
        </View>

        {/* Sign out */}
        <TouchableOpacity style={styles.signOutBtn} onPress={handleSignOut}>
          <Text style={styles.signOutText}>Sign Out</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:    { flex: 1, backgroundColor: Colors.background },
  scroll:  { flex: 1 },
  content: { padding: 20, paddingBottom: 40 },
  title:   { fontSize: 24, fontWeight: '800', color: Colors.text, marginBottom: 24 },
  section: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    marginBottom: 16,
    overflow: 'hidden',
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: Colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 6,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderLight,
  },
  rowLast:  { borderBottomWidth: 0 },
  rowLabel: { fontSize: 15, color: Colors.text, fontWeight: '500' },
  rowSub:   { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  rowValue: { fontSize: 14, color: Colors.textSecondary },
  signOutBtn: {
    marginTop: 8,
    padding: 16,
    borderRadius: 16,
    backgroundColor: Colors.errorLight,
    alignItems: 'center',
  },
  signOutText: { fontSize: 15, fontWeight: '700', color: Colors.error },
});
