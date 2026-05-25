import React from 'react';
import { View, Text, Image, TouchableOpacity, StyleSheet } from 'react-native';
import { Colors } from '../constants/Colors';
import type { Plant, CareTask } from '../types';
import { careTaskEmoji, careTaskLabel } from '../utils/scheduleUtils';
import { formatDate, isOverdue, isDueToday } from '../utils/dateUtils';

interface Props {
  plant: Plant;
  nextTask?: CareTask;
  onPress: () => void;
}

export function PlantCard({ plant, nextTask, onPress }: Props) {
  const statusColor =
    plant.status === 'healthy'         ? Colors.healthy :
    plant.status === 'needs_attention' ? Colors.needsAttention : Colors.sick;

  const taskDue    = nextTask ? formatDate(nextTask.dueDate)  : null;
  const taskIsLate = nextTask ? isOverdue(nextTask.dueDate)   : false;
  const taskToday  = nextTask ? isDueToday(nextTask.dueDate)  : false;

  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.85}>
      {/* Photo or placeholder */}
      {plant.photoUrl ? (
        <Image source={{ uri: plant.photoUrl }} style={styles.photo} />
      ) : (
        <View style={[styles.photo, styles.photoPlaceholder]}>
          <Text style={styles.plantEmoji}>🌱</Text>
        </View>
      )}

      {/* Status dot */}
      <View style={[styles.statusDot, { backgroundColor: statusColor }]} />

      <View style={styles.info}>
        <Text style={styles.name} numberOfLines={1}>{plant.name}</Text>
        <Text style={styles.species} numberOfLines={1}>{plant.species}</Text>

        {nextTask && (
          <View style={styles.taskChip}>
            <Text style={styles.taskEmoji}>{careTaskEmoji(nextTask.type)}</Text>
            <Text style={[
              styles.taskLabel,
              taskIsLate && styles.taskLate,
              taskToday  && styles.taskToday,
            ]}>
              {careTaskLabel(nextTask.type)} {taskIsLate ? '(overdue)' : taskToday ? 'today' : taskDue ?? ''}
            </Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    overflow: 'hidden',
    marginBottom: 12,
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  photo: {
    width: '100%',
    height: 140,
  },
  photoPlaceholder: {
    backgroundColor: Colors.primaryPastel,
    alignItems: 'center',
    justifyContent: 'center',
  },
  plantEmoji: { fontSize: 48 },
  statusDot: {
    position: 'absolute',
    top: 10,
    right: 10,
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#fff',
  },
  info: {
    padding: 12,
  },
  name: {
    fontSize: 15,
    fontWeight: '700',
    color: Colors.text,
  },
  species: {
    fontSize: 12,
    color: Colors.textSecondary,
    marginTop: 2,
    fontStyle: 'italic',
  },
  taskChip: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    backgroundColor: Colors.surfaceSecondary,
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    alignSelf: 'flex-start',
  },
  taskEmoji:  { fontSize: 12, marginRight: 4 },
  taskLabel:  { fontSize: 11, color: Colors.textSecondary, fontWeight: '500' },
  taskLate:   { color: Colors.error },
  taskToday:  { color: Colors.primary, fontWeight: '700' },
});
