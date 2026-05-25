import React, { useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/hooks/useAuth';
import { useCareTasks } from '@/hooks/useCareTasks';
import { usePlants } from '@/hooks/usePlants';
import { CareTaskCard } from '@/components/CareTaskCard';
import { Colors } from '@/constants/Colors';
import { format } from 'date-fns';

export default function HomeScreen() {
  const { user, profile } = useAuth();
  const router = useRouter();

  const { plants, refresh: refreshPlants } = usePlants(user?.uid);
  const {
    todayTasks,
    upcomingTasks,
    loading,
    refresh,
    complete,
    snooze,
  } = useCareTasks(user?.uid);

  useEffect(() => {
    refresh();
    refreshPlants();
  }, []);

  const firstName = profile?.displayName?.split(' ')[0] ?? 'Gardener';
  const today     = format(new Date(), 'EEEE, MMMM d');

  const healthyCount   = plants.filter((p) => p.status === 'healthy').length;
  const attentionCount = plants.filter((p) => p.status !== 'healthy').length;

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={() => { refresh(); refreshPlants(); }} />}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>Hi, {firstName}! 👋</Text>
            <Text style={styles.date}>{today}</Text>
          </View>
          <TouchableOpacity
            style={styles.analyzeBtn}
            onPress={() => router.push('/analyze')}
          >
            <Text style={styles.analyzeBtnText}>🤖 Analyze</Text>
          </TouchableOpacity>
        </View>

        {/* Stats row */}
        <View style={styles.statsRow}>
          <View style={[styles.statCard, { backgroundColor: Colors.successLight }]}>
            <Text style={styles.statNumber}>{healthyCount}</Text>
            <Text style={styles.statLabel}>Healthy</Text>
          </View>
          <View style={[styles.statCard, { backgroundColor: attentionCount > 0 ? Colors.warningLight : Colors.surfaceSecondary }]}>
            <Text style={styles.statNumber}>{attentionCount}</Text>
            <Text style={styles.statLabel}>Need Attention</Text>
          </View>
          <View style={[styles.statCard, { backgroundColor: Colors.waterLight }]}>
            <Text style={styles.statNumber}>{todayTasks.length}</Text>
            <Text style={styles.statLabel}>Due Today</Text>
          </View>
        </View>

        {/* Today's tasks */}
        <Text style={styles.sectionTitle}>📅 Due Today</Text>
        {todayTasks.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyEmoji}>🎉</Text>
            <Text style={styles.emptyText}>All caught up! No tasks due today.</Text>
          </View>
        ) : (
          todayTasks.map((task) => (
            <CareTaskCard
              key={task.id}
              task={task}
              onComplete={complete}
              onSnooze={snooze}
              onPlantPress={(id) => router.push(`/plant/${id}`)}
            />
          ))
        )}

        {/* Upcoming */}
        {upcomingTasks.length > 0 && (
          <>
            <Text style={[styles.sectionTitle, { marginTop: 8 }]}>⏳ Coming Up</Text>
            {upcomingTasks.slice(0, 5).map((task) => (
              <CareTaskCard
                key={task.id}
                task={task}
                onComplete={complete}
                onSnooze={snooze}
                onPlantPress={(id) => router.push(`/plant/${id}`)}
              />
            ))}
          </>
        )}

        {/* CTA if no plants */}
        {plants.length === 0 && (
          <TouchableOpacity
            style={styles.addFirstPlantCard}
            onPress={() => router.push('/plant/add')}
          >
            <Text style={styles.addFirstEmoji}>🌱</Text>
            <Text style={styles.addFirstTitle}>Add your first plant!</Text>
            <Text style={styles.addFirstSub}>Tap to get started</Text>
          </TouchableOpacity>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:    { flex: 1, backgroundColor: Colors.background },
  scroll:  { flex: 1 },
  content: { padding: 20, paddingBottom: 40 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  greeting:     { fontSize: 24, fontWeight: '800', color: Colors.text },
  date:         { fontSize: 13, color: Colors.textSecondary, marginTop: 2 },
  analyzeBtn: {
    backgroundColor: Colors.primary,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  analyzeBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  statsRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 24,
  },
  statCard: {
    flex: 1,
    borderRadius: 14,
    padding: 14,
    alignItems: 'center',
  },
  statNumber: { fontSize: 24, fontWeight: '800', color: Colors.text },
  statLabel:  { fontSize: 11, color: Colors.textSecondary, marginTop: 2, textAlign: 'center' },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: Colors.text, marginBottom: 12 },
  emptyState: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
    marginBottom: 16,
  },
  emptyEmoji: { fontSize: 40, marginBottom: 8 },
  emptyText:  { fontSize: 14, color: Colors.textSecondary, textAlign: 'center' },
  addFirstPlantCard: {
    marginTop: 20,
    backgroundColor: Colors.primaryPastel,
    borderRadius: 20,
    padding: 32,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: Colors.border,
    borderStyle: 'dashed',
  },
  addFirstEmoji: { fontSize: 48 },
  addFirstTitle: { fontSize: 18, fontWeight: '800', color: Colors.primaryDark, marginTop: 12 },
  addFirstSub:   { fontSize: 14, color: Colors.primary, marginTop: 4 },
});
