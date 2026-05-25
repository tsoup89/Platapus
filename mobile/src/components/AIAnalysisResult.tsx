import React, { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  Alert,
} from 'react-native';
import { Colors } from '../constants/Colors';
import { Button } from './ui/Button';
import type { AIAnalysisResult as AIResult, ScheduleAdjustment } from '../types';
import { formatRelative } from '../utils/dateUtils';

interface Props {
  result: AIResult;
  onApplyAdjustments?: (adjustments: ScheduleAdjustment[]) => Promise<void>;
}

export function AIAnalysisResult({ result, onApplyAdjustments }: Props) {
  const [applying, setApplying] = useState(false);

  const healthColor =
    result.healthStatus === 'healthy' ? Colors.success :
    result.healthStatus === 'warning' ? Colors.warning : Colors.error;

  const healthEmoji =
    result.healthStatus === 'healthy' ? '🟢' :
    result.healthStatus === 'warning' ? '🟡' : '🔴';

  const severityColor: Record<string, string> = {
    low:    Colors.success,
    medium: Colors.warning,
    high:   Colors.error,
  };

  async function handleApply() {
    if (!onApplyAdjustments || result.scheduleAdjustments.length === 0) return;
    const msg = result.scheduleAdjustments
      .map((a) => `${a.label}: ${a.currentValue ?? '?'} → ${a.recommendedValue} ${a.unit}`)
      .join('\n');
    Alert.alert(
      'Apply schedule changes?',
      msg,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Apply',
          onPress: async () => {
            setApplying(true);
            try { await onApplyAdjustments(result.scheduleAdjustments); }
            finally { setApplying(false); }
          },
        },
      ],
    );
  }

  return (
    <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
      {/* Header */}
      <View style={[styles.headerCard, { borderColor: healthColor }]}>
        <Text style={styles.healthEmoji}>{healthEmoji}</Text>
        <View style={{ flex: 1 }}>
          <Text style={[styles.healthStatus, { color: healthColor }]}>
            {result.healthStatus === 'healthy' ? 'Looking Good!' :
             result.healthStatus === 'warning' ? 'Needs Attention' : 'Critical Issues'}
          </Text>
          <Text style={styles.summary}>{result.summary}</Text>
          <Text style={styles.timestamp}>
            Analyzed {formatRelative(result.timestamp)}
          </Text>
        </View>
      </View>

      {/* Species ID */}
      {result.identifiedSpecies && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🔍 Identified As</Text>
          <Text style={styles.speciesText}>{result.identifiedSpecies}</Text>
        </View>
      )}

      {/* Issues */}
      {result.issues.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>⚠️ Issues Detected</Text>
          {result.issues.map((issue, i) => (
            <View key={i} style={styles.issueCard}>
              <View style={[styles.severityDot, { backgroundColor: severityColor[issue.severity] }]} />
              <View style={{ flex: 1 }}>
                <Text style={styles.issueType}>{issue.type}</Text>
                <Text style={styles.issueDesc}>{issue.description}</Text>
              </View>
            </View>
          ))}
        </View>
      )}

      {/* Recommendations */}
      {result.recommendations.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>💡 Recommendations</Text>
          {result.recommendations.map((rec, i) => (
            <View key={i} style={styles.recCard}>
              <Text style={styles.recAction}>{rec.action}</Text>
              <Text style={styles.recReason}>{rec.reason}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Schedule adjustments */}
      {result.scheduleAdjustments.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📅 Suggested Schedule Changes</Text>
          {result.scheduleAdjustments.map((adj, i) => (
            <View key={i} style={styles.adjRow}>
              <Text style={styles.adjLabel}>{adj.label}</Text>
              <Text style={styles.adjChange}>
                {adj.currentValue ?? '?'} → <Text style={styles.adjNew}>{adj.recommendedValue}</Text> {adj.unit}
              </Text>
              <Text style={styles.adjReason}>{adj.reason}</Text>
            </View>
          ))}

          {onApplyAdjustments && (
            <Button
              label="Apply Changes"
              icon="✅"
              onPress={handleApply}
              loading={applying}
              style={{ marginTop: 12 }}
            />
          )}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  headerCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: 16,
    gap: 12,
    borderWidth: 2,
    marginBottom: 16,
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  healthEmoji:  { fontSize: 36 },
  healthStatus: { fontSize: 18, fontWeight: '800', marginBottom: 4 },
  summary:      { fontSize: 14, color: Colors.textSecondary, lineHeight: 20 },
  timestamp:    { fontSize: 11, color: Colors.textMuted, marginTop: 6 },
  section: { marginBottom: 16 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: Colors.text, marginBottom: 10 },
  speciesText:  { fontSize: 14, color: Colors.primary, fontStyle: 'italic' },
  issueCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  severityDot: { width: 10, height: 10, borderRadius: 5, marginTop: 4 },
  issueType: { fontSize: 13, fontWeight: '700', color: Colors.text },
  issueDesc: { fontSize: 12, color: Colors.textSecondary, marginTop: 2, lineHeight: 18 },
  recCard: {
    backgroundColor: Colors.primaryPastel,
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  recAction: { fontSize: 13, fontWeight: '700', color: Colors.primaryDark },
  recReason: { fontSize: 12, color: Colors.primary, marginTop: 4, lineHeight: 18 },
  adjRow: {
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  adjLabel:  { fontSize: 13, fontWeight: '700', color: Colors.text },
  adjChange: { fontSize: 13, color: Colors.textSecondary, marginTop: 4 },
  adjNew:    { color: Colors.primary, fontWeight: '700' },
  adjReason: { fontSize: 11, color: Colors.textMuted, marginTop: 4, lineHeight: 16 },
});
