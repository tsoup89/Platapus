import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  Switch, TouchableOpacity, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/hooks/useAuth';
import { Colors } from '@/constants/Colors';
import { cancelAllNotifications } from '@/services/notificationService';
import { getSeasonBannerInfo } from '@/utils/seasonUtils';
import type { Hemisphere } from '@/types';

export default function SettingsScreen() {
  const { profile, signOut, updateNotificationPrefs, updateHemisphere } = useAuth();
  const prefs = profile?.notificationPreferences;
  const hemisphere = profile?.hemisphere ?? 'north';

  const [notificationsOn, setNotificationsOn] = useState(prefs?.enabled ?? true);
  const season = getSeasonBannerInfo(hemisphere);

  async function toggleNotifications(value: boolean) {
    setNotificationsOn(value);
    if (!value) await cancelAllNotifications();
    await updateNotificationPrefs({ ...prefs!, enabled: value });
  }

  async function handleHemisphere(h: Hemisphere) {
    await updateHemisphere(h);
  }

  function handleSignOut() {
    Alert.alert('Sign out', 'Are you sure?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign Out', style: 'destructive', onPress: signOut },
    ]);
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        <Text style={styles.title}>Settings ⚙️</Text>

        {/* Account */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Account</Text>
          <Row label="Name"  value={profile?.displayName ?? '—'} />
          <Row label="Email" value={profile?.email ?? '—'} last />
        </View>

        {/* Seasonal care */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Seasonal Care</Text>
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowLabel}>Hemisphere</Text>
              <Text style={styles.rowSub}>
                Currently {season.emoji} {season.label} — watering {season.mult < 1 ? 'more' : season.mult > 1 ? 'less' : 'at normal'} frequency
              </Text>
            </View>
          </View>
          <View style={[styles.row, styles.rowLast]}>
            <TouchableOpacity
              style={[
                styles.hemiBtn,
                hemisphere === 'north' && styles.hemiBtnActive,
              ]}
              onPress={() => handleHemisphere('north')}
            >
              <Text style={[styles.hemiBtnText, hemisphere === 'north' && styles.hemiBtnTextActive]}>
                🌍 North
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.hemiBtn,
                hemisphere === 'south' && styles.hemiBtnActive,
              ]}
              onPress={() => handleHemisphere('south')}
            >
              <Text style={[styles.hemiBtnText, hemisphere === 'south' && styles.hemiBtnTextActive]}>
                🌏 South
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Notifications */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Notifications</Text>
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowLabel}>Care Reminders</Text>
              <Text style={styles.rowSub}>Notify when it\'s time to water, fertilize, etc.</Text>
            </View>
            <Switch
              value={notificationsOn}
              onValueChange={toggleNotifications}
              trackColor={{ false: Colors.border, true: Colors.primaryLight }}
              thumbColor={notificationsOn ? Colors.primary : '#f4f4f4'}
            />
          </View>
          <Row
            label="Reminder time"
            value={`${String(prefs?.dailyReminderHour ?? 8).padStart(2,'0')}:${String(prefs?.dailyReminderMinute ?? 0).padStart(2,'0')}`}
            last
          />
        </View>

        {/* About */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>About</Text>
          <Row label="App"           value="Gamgee v1.0" />
          <Row label="AI powered by" value="Claude (Anthropic) 🤖" last />
        </View>

        <TouchableOpacity style={styles.signOutBtn} onPress={handleSignOut}>
          <Text style={styles.signOutText}>Sign Out</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

function Row({ label, value, last = false }: { label: string; value: string; last?: boolean }) {
  return (
    <View style={[styles.row, last && styles.rowLast]}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe:    { flex: 1, backgroundColor: Colors.background },
  scroll:  { flex: 1 },
  content: { padding: 20, paddingBottom: 40 },
  title:   { fontSize: 24, fontWeight: '800', color: Colors.text, marginBottom: 24 },
  section: {
    backgroundColor: Colors.surface, borderRadius: 16, marginBottom: 16,
    overflow: 'hidden', shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 6, elevation: 2,
  },
  sectionTitle: {
    fontSize: 12, fontWeight: '700', color: Colors.textMuted,
    textTransform: 'uppercase', letterSpacing: 0.8,
    paddingHorizontal: 16, paddingTop: 14, paddingBottom: 6,
  },
  row: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 14,
    borderBottomWidth: 1, borderBottomColor: Colors.borderLight,
  },
  rowLast:  { borderBottomWidth: 0 },
  rowLabel: { fontSize: 15, color: Colors.text, fontWeight: '500' },
  rowSub:   { fontSize: 12, color: Colors.textMuted, marginTop: 2 },
  rowValue: { fontSize: 14, color: Colors.textSecondary },
  hemiBtn: {
    flex: 1, marginHorizontal: 4, paddingVertical: 10,
    borderRadius: 12, borderWidth: 1, borderColor: Colors.border,
    alignItems: 'center',
  },
  hemiBtnActive:     { backgroundColor: Colors.primary, borderColor: Colors.primary },
  hemiBtnText:       { fontSize: 14, fontWeight: '600', color: Colors.textSecondary },
  hemiBtnTextActive: { color: '#fff' },
  signOutBtn:  { marginTop: 8, padding: 16, borderRadius: 16, backgroundColor: Colors.errorLight, alignItems: 'center' },
  signOutText: { fontSize: 15, fontWeight: '700', color: Colors.error },
});
