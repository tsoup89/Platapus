import React, { useMemo } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { format, subDays, addDays, startOfWeek } from 'date-fns';
import { Colors } from '../constants/Colors';
import type { CareHistoryEntry } from '../services/careHistoryService';

const WEEKS     = 8;
const CELL_SIZE = 34;
const CELL_GAP  = 4;
const DAY_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

const TYPE_COLORS: Record<string, string> = {
  water:     Colors.water,
  fertilize: Colors.fertilize,
  repot:     Colors.repot,
  trim:      Colors.trim,
  mist:      Colors.mist,
  custom:    Colors.custom,
};

interface Props {
  history: CareHistoryEntry[];
}

export function CareActivityCalendar({ history }: Props) {
  const today = useMemo(() => {
    const d = new Date();
    d.setHours(12, 0, 0, 0);
    return d;
  }, []);

  const todayKey = format(today, 'yyyy-MM-dd');

  // Build event map: 'yyyy-MM-dd' → Set of care types
  const eventMap = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const entry of history) {
      const key = entry.date.slice(0, 10);
      const set = map.get(key) ?? new Set<string>();
      set.add(entry.type);
      map.set(key, set);
    }
    return map;
  }, [history]);

  // Build grid: start from Monday of (WEEKS) weeks ago
  const columns = useMemo(() => {
    const startOfGrid = startOfWeek(
      subDays(today, WEEKS * 7 - 1),
      { weekStartsOn: 1 },
    );
    const cols: Date[][] = [];
    let cursor = new Date(startOfGrid);

    while (cursor <= today) {
      const week: Date[] = [];
      for (let d = 0; d < 7; d++) {
        week.push(new Date(cursor));
        cursor = addDays(cursor, 1);
      }
      cols.push(week);
    }
    return cols;
  }, [today]);

  return (
    <View style={styles.wrapper}>
      {/* Grid */}
      <View style={styles.grid}>
        {/* Day-of-week labels */}
        <View style={styles.dayLabelCol}>
          {DAY_LABELS.map((label, i) => (
            <Text key={i} style={styles.dayLabel}>{label}</Text>
          ))}
        </View>

        {/* Week columns */}
        <View style={styles.weeksRow}>
          {columns.map((week, wi) => (
            <View key={wi} style={styles.weekCol}>
              {week.map((day) => {
                const key   = format(day, 'yyyy-MM-dd');
                const types = eventMap.get(key);
                const count = types?.size ?? 0;
                const isToday  = key === todayKey;
                const isFuture = day > today;

                return (
                  <View
                    key={key}
                    style={[
                      styles.cell,
                      isFuture  && styles.cellFuture,
                      count > 0 && styles.cellActive,
                      count >= 3 && styles.cellVeryActive,
                      isToday   && styles.cellToday,
                    ]}
                  >
                    {types && Array.from(types).slice(0, 4).map((type, ti) => (
                      <View
                        key={ti}
                        style={[styles.dot, { backgroundColor: TYPE_COLORS[type] ?? Colors.primary }]}
                      />
                    ))}
                  </View>
                );
              })}
            </View>
          ))}
        </View>
      </View>

      {/* Legend */}
      <View style={styles.legend}>
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <View key={type} style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: color }]} />
            <Text style={styles.legendLabel}>{type}</Text>
          </View>
        ))}
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { borderWidth: 2, borderColor: Colors.primary, backgroundColor: 'transparent' }]} />
          <Text style={styles.legendLabel}>today</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {},
  grid: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  dayLabelCol: {
    width: 16,
    marginRight: 6,
    paddingTop: 2,
  },
  dayLabel: {
    fontSize: 10,
    color: Colors.textMuted,
    height: CELL_SIZE + CELL_GAP,
    lineHeight: CELL_SIZE,
    textAlign: 'center',
  },
  weeksRow: {
    flexDirection: 'row',
    gap: CELL_GAP,
    flexWrap: 'nowrap',
  },
  weekCol: {
    gap: CELL_GAP,
  },
  cell: {
    width:         CELL_SIZE,
    height:        CELL_SIZE,
    borderRadius:  8,
    backgroundColor: Colors.borderLight,
    flexDirection: 'row',
    flexWrap:      'wrap',
    alignItems:    'center',
    justifyContent:'center',
    gap: 3,
    padding: 5,
  },
  cellFuture: {
    backgroundColor: 'transparent',
    borderWidth:     1,
    borderColor:     Colors.borderLight,
    borderStyle:     'dashed',
  },
  cellActive: {
    backgroundColor: Colors.primaryPastel,
  },
  cellVeryActive: {
    backgroundColor: Colors.primaryLight + '50',
  },
  cellToday: {
    borderWidth: 2,
    borderColor: Colors.primary,
  },
  dot: {
    width:        9,
    height:       9,
    borderRadius: 5,
  },
  legend: {
    flexDirection: 'row',
    flexWrap:      'wrap',
    gap: 10,
    marginTop: 14,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems:    'center',
    gap: 5,
  },
  legendDot: {
    width:        9,
    height:       9,
    borderRadius: 5,
  },
  legendLabel: {
    fontSize: 11,
    color:    Colors.textSecondary,
    textTransform: 'capitalize',
  },
});
