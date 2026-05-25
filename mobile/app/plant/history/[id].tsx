import React, { useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/hooks/useAuth';
import { usePlants } from '@/hooks/usePlants';
import { usePlantHistory } from '@/hooks/useCareHistory';
import { CareActivityCalendar } from '@/components/CareActivityCalendar';
import { CareHistoryTimeline } from '@/components/CareHistoryTimeline';
import { Colors } from '@/constants/Colors';

export default function PlantHistoryScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router  = useRouter();
  const { user } = useAuth();

  const { plants, refresh }                       = usePlants(user?.uid);
  const { history, loading, refresh: refreshHist } = usePlantHistory(id);

  const plant = plants.find((p) => p.id === id);

  useEffect(() => {
    refresh();
    refreshHist();
  }, []);

  // Stats derived from history
  const count = (type: string) => history.filter((h) => h.type === type).length;

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        <Text style={styles.heading}>
          {plant ? `${plant.name}` : 'Plant'} — Care History
        </Text>

        {loading ? (
          <ActivityIndicator color={Colors.primary} style={{ marginTop: 40 }} />
        ) : (
          <>
            {/* 8-week activity calendar */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Activity — last 8 weeks</Text>
              <CareActivityCalendar history={history} />
            </View>

            {/* Quick stats */}
            {history.length > 0 && (
              <View style={styles.statsRow}>
                <StatCard emoji="💧" label="Waterings"  value={count('water')} />
                <StatCard emoji="✨"   label="Fertilized" value={count('fertilize')} />
                <StatCard emoji="✂️"   label="Trimmed"   value={count('trim')} />
                <StatCard emoji="🪣"  label="Repotted"  value={count('repot')} />
              </View>
            )}

            {/* Full timeline */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Full Timeline</Text>
              <CareHistoryTimeline history={history} limit={200} />
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function StatCard({
  emoji,
  label,
  value,
}: {
  emoji: string;
  label: string;
  value: number;
}) {
  return (
    <View style={styles.statCard}>
      <Text style={styles.statEmoji}>{emoji}</Text>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe:    { flex: 1, backgroundColor: Colors.background },
  scroll:  { flex: 1 },
  content: { padding: 20, paddingBottom: 40 },
  heading: { fontSize: 22, fontWeight: '800', color: Colors.text, marginBottom: 20 },
  section: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 14,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  statCard: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: 14,
    padding: 12,
    alignItems: 'center',
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 5,
    elevation: 2,
  },
  statEmoji: { fontSize: 22, marginBottom: 4 },
  statValue: { fontSize: 20, fontWeight: '800', color: Colors.text },
  statLabel: { fontSize: 10, color: Colors.textSecondary, marginTop: 2, textAlign: 'center' },
});
