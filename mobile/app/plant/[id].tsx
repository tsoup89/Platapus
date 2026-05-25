import React, { useEffect } from 'react';
import {
  View, Text, ScrollView, Image, StyleSheet,
  TouchableOpacity, Alert, ActivityIndicator,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/hooks/useAuth';
import { usePlants } from '@/hooks/usePlants';
import { useCareTasks } from '@/hooks/useCareTasks';
import { usePlantHistory } from '@/hooks/useCareHistory';
import { Colors } from '@/constants/Colors';
import { CareHistoryTimeline } from '@/components/CareHistoryTimeline';
import { careTaskEmoji, careTaskLabel, lightLabel, humidityLabel } from '@/utils/scheduleUtils';
import { formatDate, formatRelative } from '@/utils/dateUtils';

export default function PlantDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router  = useRouter();
  const { user } = useAuth();

  const { plants, loading: plantsLoading, refresh, markDone, remove } = usePlants(user?.uid);
  const { tasks, refresh: refreshTasks, complete }                    = useCareTasks(user?.uid);
  const { history, refresh: refreshHistory }                          = usePlantHistory(id);

  const plant = plants.find((p) => p.id === id);

  useEffect(() => {
    refresh();
    refreshTasks();
    refreshHistory();
  }, []);

  const plantTasks = tasks.filter((t) => t.plantId === id);

  async function handleDelete() {
    if (!plant) return;
    Alert.alert(
      'Delete plant',
      `Remove ${plant.name} from your collection?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => { await remove(plant); router.back(); },
        },
      ],
    );
  }

  if (plantsLoading) {
    return <View style={styles.loader}><ActivityIndicator size="large" color={Colors.primary} /></View>;
  }
  if (!plant) {
    return <View style={styles.loader}><Text style={{ color: Colors.textSecondary }}>Plant not found.</Text></View>;
  }

  const statusColor =
    plant.status === 'healthy'         ? Colors.healthy :
    plant.status === 'needs_attention' ? Colors.needsAttention : Colors.sick;

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>

        {/* Hero photo */}
        {plant.photoUrl ? (
          <Image source={{ uri: plant.photoUrl }} style={styles.heroPhoto} />
        ) : (
          <View style={styles.heroPlaceholder}>
            <Text style={{ fontSize: 72 }}>🌱</Text>
          </View>
        )}

        {/* Quick actions */}
        <View style={styles.quickActions}>
          <QuickBtn emoji="🤖" label="Analyze"   onPress={() => router.push({ pathname: '/analyze', params: { plantId: id } })} />
          <QuickBtn emoji="💧" label="Watered"   onPress={() => markDone(plant, 'water')} />
          <QuickBtn emoji="✨"   label="Fertilized" onPress={() => markDone(plant, 'fertilize')} />
          <QuickBtn emoji="🗑️" label="Delete"    onPress={handleDelete} danger />
        </View>

        {/* Name + status */}
        <View style={styles.nameRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.plantName}>{plant.name}</Text>
            <Text style={styles.plantSpecies}>{plant.species}</Text>
            {plant.roomName && <Text style={styles.plantRoom}>📍 {plant.roomName}</Text>}
          </View>
          <View style={[styles.statusBadge, { backgroundColor: statusColor + '22' }]}>
            <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
            <Text style={[styles.statusText, { color: statusColor }]}>
              {plant.status === 'healthy' ? 'Healthy' :
               plant.status === 'needs_attention' ? 'Attention' : 'Sick'}
            </Text>
          </View>
        </View>

        {/* Care profile */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Care Profile</Text>
          <View style={styles.careGrid}>
            <CareItem emoji="💧" label="Water every"    value={`${plant.careProfile.wateringFrequencyDays} days`} />
            <CareItem emoji="☀️" label="Light"          value={lightLabel(plant.careProfile.lightRequirement)} />
            <CareItem emoji="🌫️" label="Humidity"      value={humidityLabel(plant.careProfile.humidityRequirement)} />
            {plant.careProfile.fertilizingFrequencyDays && (
              <CareItem emoji="✨" label="Fertilize every" value={`${plant.careProfile.fertilizingFrequencyDays} days`} />
            )}
            {plant.careProfile.repottingFrequencyMonths && (
              <CareItem emoji="🪣" label="Repot every"    value={`${plant.careProfile.repottingFrequencyMonths} months`} />
            )}
            {plant.careProfile.trimmingFrequencyDays && (
              <CareItem emoji="✂️" label="Trim every"     value={`${plant.careProfile.trimmingFrequencyDays} days`} />
            )}
          </View>
        </View>

        {/* Upcoming tasks */}
        {plantTasks.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Upcoming Tasks</Text>
            {plantTasks.map((task) => (
              <View key={task.id} style={styles.taskRow}>
                <Text style={styles.taskEmoji}>{careTaskEmoji(task.type)}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.taskLabel}>{careTaskLabel(task.type)}</Text>
                  <Text style={styles.taskDue}>{formatDate(task.dueDate)}</Text>
                </View>
                <TouchableOpacity style={styles.completeBtn} onPress={() => complete(task.id)}>
                  <Text style={styles.completeBtnText}>Done</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}

        {/* Recent care history — mini preview */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Care History</Text>
            <TouchableOpacity onPress={() => router.push(`/plant/history/${id}`)}>
              <Text style={styles.seeAll}>See all ›</Text>
            </TouchableOpacity>
          </View>
          <CareHistoryTimeline history={history} limit={5} />
        </View>

        {/* Last AI analysis */}
        {plant.lastAnalysisNotes && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>🤖 Last AI Analysis</Text>
            {plant.lastAnalyzed && (
              <Text style={styles.analysisDate}>{formatRelative(plant.lastAnalyzed)}</Text>
            )}
            <Text style={styles.analysisNotes}>{plant.lastAnalysisNotes}</Text>
            <TouchableOpacity
              style={styles.analyzeAgainBtn}
              onPress={() => router.push({ pathname: '/analyze', params: { plantId: id } })}
            >
              <Text style={styles.analyzeAgainText}>🤖 Analyze again</Text>
            </TouchableOpacity>
          </View>
        )}

        {plant.notes && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Notes</Text>
            <Text style={styles.notes}>{plant.notes}</Text>
          </View>
        )}

        <Text style={styles.addedDate}>Added {formatDate(plant.dateAdded)}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function QuickBtn({
  emoji, label, onPress, danger = false,
}: {
  emoji: string; label: string; onPress: () => void; danger?: boolean;
}) {
  return (
    <TouchableOpacity
      style={[styles.quickBtn, danger && { backgroundColor: Colors.errorLight }]}
      onPress={onPress}
    >
      <Text style={styles.quickBtnEmoji}>{emoji}</Text>
      <Text style={[styles.quickBtnLabel, danger && { color: Colors.error }]}>{label}</Text>
    </TouchableOpacity>
  );
}

function CareItem({ emoji, label, value }: { emoji: string; label: string; value: string }) {
  return (
    <View style={styles.careItem}>
      <Text style={styles.careEmoji}>{emoji}</Text>
      <Text style={styles.careLabel}>{label}</Text>
      <Text style={styles.careValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe:    { flex: 1, backgroundColor: Colors.background },
  scroll:  { flex: 1 },
  content: { paddingBottom: 40 },
  loader:  { flex: 1, alignItems: 'center', justifyContent: 'center' },

  heroPhoto:       { width: '100%', height: 260 },
  heroPlaceholder: { width: '100%', height: 200, backgroundColor: Colors.primaryPastel, alignItems: 'center', justifyContent: 'center' },

  quickActions: {
    flexDirection: 'row',
    gap: 8,
    padding: 14,
    backgroundColor: Colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderLight,
  },
  quickBtn: {
    flex: 1,
    backgroundColor: Colors.surfaceSecondary,
    borderRadius: 12,
    padding: 10,
    alignItems: 'center',
  },
  quickBtnEmoji: { fontSize: 20 },
  quickBtnLabel: { fontSize: 10, color: Colors.textSecondary, fontWeight: '600', marginTop: 4 },

  nameRow: { flexDirection: 'row', alignItems: 'flex-start', padding: 16, gap: 12 },
  plantName:    { fontSize: 22, fontWeight: '800', color: Colors.text },
  plantSpecies: { fontSize: 14, color: Colors.textSecondary, fontStyle: 'italic', marginTop: 2 },
  plantRoom:    { fontSize: 13, color: Colors.textMuted, marginTop: 4 },
  statusBadge:  { flexDirection: 'row', alignItems: 'center', borderRadius: 20, paddingHorizontal: 10, paddingVertical: 6, gap: 6 },
  statusDot:    { width: 8, height: 8, borderRadius: 4 },
  statusText:   { fontSize: 12, fontWeight: '700' },

  section: {
    margin: 16, marginTop: 0,
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: 16,
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle:  { fontSize: 13, fontWeight: '700', color: Colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.6 },
  seeAll:        { fontSize: 13, color: Colors.primary, fontWeight: '700' },

  careGrid:  { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  careItem:  { backgroundColor: Colors.surfaceSecondary, borderRadius: 12, padding: 12, minWidth: '45%', flex: 1 },
  careEmoji: { fontSize: 20, marginBottom: 6 },
  careLabel: { fontSize: 11, color: Colors.textMuted, fontWeight: '600' },
  careValue: { fontSize: 13, color: Colors.text, fontWeight: '700', marginTop: 2 },

  taskRow:        { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: Colors.borderLight },
  taskEmoji:      { fontSize: 20 },
  taskLabel:      { fontSize: 14, fontWeight: '600', color: Colors.text },
  taskDue:        { fontSize: 12, color: Colors.textSecondary, marginTop: 2 },
  completeBtn:    { backgroundColor: Colors.primary, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 },
  completeBtnText:{ fontSize: 12, color: '#fff', fontWeight: '700' },

  analysisDate:    { fontSize: 12, color: Colors.textMuted, marginBottom: 6 },
  analysisNotes:   { fontSize: 14, color: Colors.textSecondary, lineHeight: 20 },
  analyzeAgainBtn: { marginTop: 12, alignSelf: 'flex-start', backgroundColor: Colors.primaryPastel, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  analyzeAgainText:{ fontSize: 13, color: Colors.primary, fontWeight: '700' },

  notes:     { fontSize: 14, color: Colors.textSecondary, lineHeight: 20 },
  addedDate: { textAlign: 'center', fontSize: 12, color: Colors.textMuted, padding: 16 },
});
