import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Alert } from 'react-native';
import * as Haptics from 'expo-haptics';
import { Colors } from '../constants/Colors';
import type { CareTask } from '../types';
import { careTaskEmoji, careTaskLabel } from '../utils/scheduleUtils';
import { formatDate, isOverdue, isDueToday } from '../utils/dateUtils';

interface Props {
  task: CareTask;
  onComplete: (taskId: string) => void;
  onSnooze: (taskId: string, days: number) => void;
  onPlantPress?: (plantId: string) => void;
}

export function CareTaskCard({ task, onComplete, onSnooze, onPlantPress }: Props) {
  const overdue  = isOverdue(task.dueDate);
  const today    = isDueToday(task.dueDate);
  const typeColor = (Colors as any)[task.type] as string ?? Colors.primary;
  const typeBg    = (Colors as any)[`${task.type}Light`] as string ?? Colors.primaryPastel;

  function handleComplete() {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    onComplete(task.id);
  }

  function handleSnooze() {
    Alert.alert(
      'Snooze reminder',
      'Push this task back by:',
      [
        { text: '1 day',    onPress: () => onSnooze(task.id, 1) },
        { text: '3 days',   onPress: () => onSnooze(task.id, 3) },
        { text: '1 week',   onPress: () => onSnooze(task.id, 7) },
        { text: 'Cancel',   style: 'cancel' },
      ],
    );
  }

  return (
    <View style={[styles.card, overdue && styles.cardOverdue]}>
      {/* Type badge */}
      <View style={[styles.badge, { backgroundColor: typeBg }]}>
        <Text style={styles.badgeEmoji}>{careTaskEmoji(task.type)}</Text>
        <Text style={[styles.badgeLabel, { color: typeColor }]}>
          {careTaskLabel(task.type)}
        </Text>
      </View>

      <View style={styles.body}>
        <TouchableOpacity onPress={() => onPlantPress?.(task.plantId)}>
          <Text style={styles.plantName}>{task.plantName}</Text>
        </TouchableOpacity>
        <Text style={[
          styles.dueDate,
          overdue && styles.dueDateOverdue,
          today   && styles.dueDateToday,
        ]}>
          {overdue ? '⚠️ Overdue — ' : '📅 '}
          {formatDate(task.dueDate)}
        </Text>
      </View>

      <View style={styles.actions}>
        <TouchableOpacity style={styles.snoozeBtn} onPress={handleSnooze}>
          <Text style={styles.snoozeBtnText}>Snooze</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.doneBtn} onPress={handleComplete}>
          <Text style={styles.doneBtnText}>✓ Done</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
    gap: 10,
  },
  cardOverdue: {
    borderLeftWidth: 3,
    borderLeftColor: Colors.error,
  },
  badge: {
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 8,
    alignItems: 'center',
    minWidth: 64,
  },
  badgeEmoji: { fontSize: 20 },
  badgeLabel: { fontSize: 11, fontWeight: '700', marginTop: 2 },
  body: { flex: 1 },
  plantName: { fontSize: 14, fontWeight: '700', color: Colors.text },
  dueDate:       { fontSize: 12, color: Colors.textSecondary, marginTop: 2 },
  dueDateOverdue:{ color: Colors.error },
  dueDateToday:  { color: Colors.primary, fontWeight: '700' },
  actions: { flexDirection: 'column', gap: 6 },
  snoozeBtn: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  snoozeBtnText: { fontSize: 12, color: Colors.textSecondary },
  doneBtn: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    backgroundColor: Colors.primary,
  },
  doneBtnText: { fontSize: 12, color: '#fff', fontWeight: '700' },
});
