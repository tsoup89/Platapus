import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { format } from 'date-fns';
import { Colors } from '../constants/Colors';
import type { CareHistoryEntry } from '../services/careHistoryService';
import { careTaskEmoji, careTaskLabel } from '../utils/scheduleUtils';
import { formatDate } from '../utils/dateUtils';

interface Props {
  history: CareHistoryEntry[];
  showPlantName?: boolean; // useful when showing history across all plants
  limit?: number;
}

export function CareHistoryTimeline({
  history,
  showPlantName = false,
  limit = 40,
}: Props) {
  if (history.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyEmoji}>📝</Text>
        <Text style={styles.emptyText}>
          No care history yet.{"\n"}Complete your first task to start tracking!
        </Text>
      </View>
    );
  }

  // Group by day: 'yyyy-MM-dd' → entries[]
  const grouped = new Map<string, CareHistoryEntry[]>();
  for (const entry of history.slice(0, limit)) {
    const key = entry.date.slice(0, 10);
    const arr = grouped.get(key) ?? [];
    arr.push(entry);
    grouped.set(key, arr);
  }

  return (
    <View>
      {Array.from(grouped.entries()).map(([dateKey, entries]) => (
        <View key={dateKey} style={styles.group}>
          {/* Date header */}
          <Text style={styles.dateHeader}>
            {formatDate(`${dateKey}T12:00:00.000Z`)}
          </Text>

          {/* Events for that day */}
          <View style={styles.card}>
            {entries.map((entry, i) => (
              <View
                key={`${entry.id}-${i}`}
                style={[
                  styles.row,
                  i < entries.length - 1 && styles.rowDivider,
                ]}
              >
                {/* Type badge */}
                <View style={[styles.badge, { backgroundColor: (Colors as any)[`${entry.type}Light`] ?? Colors.primaryPastel }]}>
                  <Text style={styles.badgeEmoji}>{careTaskEmoji(entry.type)}</Text>
                </View>

                {/* Info */}
                <View style={styles.info}>
                  <Text style={styles.label}>{careTaskLabel(entry.type)}</Text>
                  {showPlantName && (
                    <Text style={styles.plantName}>{entry.plantName}</Text>
                  )}
                </View>

                {/* Time */}
                <Text style={styles.time}>
                  {format(new Date(entry.date), 'h:mm a')}
                </Text>
              </View>
            ))}
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  empty: { alignItems: 'center', paddingVertical: 32, paddingHorizontal: 24 },
  emptyEmoji: { fontSize: 36, marginBottom: 10 },
  emptyText: {
    fontSize: 13,
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
  },
  group: { marginBottom: 18 },
  dateHeader: {
    fontSize: 12,
    fontWeight: '700',
    color: Colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 8,
  },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 14,
    overflow: 'hidden',
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 5,
    elevation: 2,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 12,
  },
  rowDivider: {
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderLight,
  },
  badge: {
    width: 38,
    height: 38,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeEmoji: { fontSize: 18 },
  info:       { flex: 1 },
  label:      { fontSize: 14, fontWeight: '600', color: Colors.text },
  plantName:  { fontSize: 12, color: Colors.textSecondary, marginTop: 2 },
  time:       { fontSize: 12, color: Colors.textMuted },
});
