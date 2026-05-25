import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import type { PestDetectionResult, PestOrDiseaseIssue, PestIssueType } from '../types';
import { Colors } from '../constants/Colors';

// ─── Severity config ──────────────────────────────────────────────────────────

const SEVERITY_CONFIG = {
  clean: {
    emoji: '✅',
    label: 'All Clear!',
    subtitle: 'No pests or diseases detected.',
    bg: '#e8f5e9',
    text: '#1b5e20',
    border: '#4caf50',
  },
  warning: {
    emoji: '⚠️',
    label: 'Watch Out',
    subtitle: 'Early signs detected — act now to stop spread.',
    bg: '#fff8e1',
    text: '#e65100',
    border: '#ff9800',
  },
  infestation: {
    emoji: '🚨',
    label: 'Active Problem',
    subtitle: 'Significant infestation or disease — treat immediately.',
    bg: '#ffebee',
    text: '#b71c1c',
    border: '#f44336',
  },
};

const TYPE_ICONS: Record<PestIssueType, string> = {
  pest:        '🐛',
  disease:     '🍄',
  deficiency:  '🌿',
};

const CONFIDENCE_COLORS: Record<string, string> = {
  high:   '#2e7d32',
  medium: '#f57c00',
  low:    '#757575',
};

const SEVERITY_COLORS: Record<string, string> = {
  low:    '#388e3c',
  medium: '#f57c00',
  high:   '#c62828',
};

// ─── Issue card ───────────────────────────────────────────────────────────────

function IssueCard({ issue }: { issue: PestOrDiseaseIssue }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <View style={issueStyles.card}>
      {/* Header row */}
      <TouchableOpacity
        style={issueStyles.header}
        onPress={() => setExpanded(e => !e)}
        activeOpacity={0.7}
      >
        <Text style={issueStyles.typeIcon}>{TYPE_ICONS[issue.type]}</Text>
        <View style={issueStyles.nameBlock}>
          <Text style={issueStyles.name}>{issue.name}</Text>
          <Text style={issueStyles.typeLabel}>{issue.type}</Text>
        </View>
        <View style={issueStyles.badges}>
          <View style={[issueStyles.badge, { backgroundColor: CONFIDENCE_COLORS[issue.confidence] + '22' }]}>
            <Text style={[issueStyles.badgeText, { color: CONFIDENCE_COLORS[issue.confidence] }]}>
              {issue.confidence} confidence
            </Text>
          </View>
          <View style={[issueStyles.badge, { backgroundColor: SEVERITY_COLORS[issue.severity] + '22' }]}>
            <Text style={[issueStyles.badgeText, { color: SEVERITY_COLORS[issue.severity] }]}>
              {issue.severity} severity
            </Text>
          </View>
        </View>
        <Text style={issueStyles.chevron}>{expanded ? '▲' : '▼'}</Text>
      </TouchableOpacity>

      {/* Expanded details */}
      {expanded && (
        <View style={issueStyles.details}>
          <View style={issueStyles.section}>
            <Text style={issueStyles.sectionLabel}>🔍 What we see</Text>
            <Text style={issueStyles.sectionText}>{issue.symptoms}</Text>
          </View>
          <View style={issueStyles.section}>
            <Text style={issueStyles.sectionLabel}>💊 Treatment</Text>
            <Text style={issueStyles.sectionText}>{issue.treatment}</Text>
          </View>
          <View style={issueStyles.section}>
            <Text style={issueStyles.sectionLabel}>🛡️ Prevention</Text>
            <Text style={issueStyles.sectionText}>{issue.prevention}</Text>
          </View>
        </View>
      )}
    </View>
  );
}

const issueStyles = StyleSheet.create({
  card:       { backgroundColor: Colors.surface, borderRadius: 14, marginBottom: 10, overflow: 'hidden', borderWidth: 1, borderColor: Colors.border },
  header:     { flexDirection: 'row', alignItems: 'center', padding: 14, gap: 10 },
  typeIcon:   { fontSize: 22 },
  nameBlock:  { flex: 1 },
  name:       { fontSize: 15, fontWeight: '700', color: Colors.text },
  typeLabel:  { fontSize: 11, color: Colors.textMuted, textTransform: 'capitalize', marginTop: 1 },
  badges:     { flexDirection: 'column', gap: 4, alignItems: 'flex-end' },
  badge:      { borderRadius: 8, paddingHorizontal: 7, paddingVertical: 2 },
  badgeText:  { fontSize: 10, fontWeight: '600' },
  chevron:    { fontSize: 12, color: Colors.textMuted, marginLeft: 4 },
  details:    { borderTopWidth: 1, borderTopColor: Colors.border, padding: 14, gap: 12 },
  section:    { gap: 4 },
  sectionLabel: { fontSize: 12, fontWeight: '700', color: Colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.5 },
  sectionText:  { fontSize: 13, color: Colors.text, lineHeight: 20 },
});

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  result: PestDetectionResult;
}

export function PestDetectionResultView({ result }: Props) {
  const severity = SEVERITY_CONFIG[result.overallSeverity];

  return (
    <View style={styles.container}>
      {/* Severity banner */}
      <View style={[styles.severityBanner, { backgroundColor: severity.bg, borderColor: severity.border }]}>
        <Text style={styles.severityEmoji}>{severity.emoji}</Text>
        <View style={styles.severityText}>
          <Text style={[styles.severityLabel, { color: severity.text }]}>{severity.label}</Text>
          <Text style={[styles.severitySubtitle, { color: severity.text }]}>{severity.subtitle}</Text>
        </View>
      </View>

      {/* Summary */}
      <Text style={styles.summary}>{result.summary}</Text>

      {/* Quarantine warning */}
      {result.quarantineRecommended && (
        <View style={styles.quarantineBanner}>
          <Text style={styles.quarantineText}>
            🔴 Quarantine recommended — isolate this plant from others immediately to prevent spread.
          </Text>
        </View>
      )}

      {/* Immediate actions */}
      {result.immediateActions?.length > 0 && (
        <View style={styles.actionsBox}>
          <Text style={styles.sectionTitle}>⚡ Immediate Actions</Text>
          {result.immediateActions.map((action, i) => (
            <View key={i} style={styles.actionRow}>
              <Text style={styles.actionBullet}>{i + 1}</Text>
              <Text style={styles.actionText}>{action}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Issues */}
      {result.issues?.length > 0 ? (
        <View>
          <Text style={styles.sectionTitle}>🔬 Findings ({result.issues.length})</Text>
          <Text style={styles.tapHint}>Tap each card for treatment details</Text>
          {result.issues.map((issue, i) => (
            <IssueCard key={i} issue={issue} />
          ))}
        </View>
      ) : result.overallSeverity === 'clean' ? (
        <View style={styles.cleanBox}>
          <Text style={styles.cleanText}>🌿 Your plant looks healthy! No issues detected in this scan.</Text>
        </View>
      ) : null}

      <Text style={styles.disclaimer}>
        AI analysis is a guide only. For severe infestations, consult a local nursery or extension service.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container:        { gap: 16 },
  severityBanner:   { flexDirection: 'row', alignItems: 'center', borderRadius: 16, padding: 16, gap: 14, borderWidth: 2 },
  severityEmoji:    { fontSize: 36 },
  severityText:     { flex: 1 },
  severityLabel:    { fontSize: 18, fontWeight: '800' },
  severitySubtitle: { fontSize: 12, marginTop: 2, lineHeight: 18 },
  summary:          { fontSize: 14, color: Colors.text, lineHeight: 22, backgroundColor: Colors.surfaceSecondary, borderRadius: 12, padding: 14 },
  quarantineBanner: { backgroundColor: '#ffebee', borderRadius: 12, padding: 14, borderLeftWidth: 4, borderLeftColor: '#f44336' },
  quarantineText:   { fontSize: 13, color: '#b71c1c', lineHeight: 20, fontWeight: '600' },
  actionsBox:       { backgroundColor: Colors.surface, borderRadius: 14, padding: 14, borderWidth: 1, borderColor: Colors.border, gap: 8 },
  actionRow:        { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  actionBullet:     { width: 22, height: 22, borderRadius: 11, backgroundColor: Colors.primary, color: '#fff', fontSize: 12, fontWeight: '800', textAlign: 'center', lineHeight: 22 },
  actionText:       { flex: 1, fontSize: 13, color: Colors.text, lineHeight: 20 },
  sectionTitle:     { fontSize: 15, fontWeight: '700', color: Colors.text, marginBottom: 4 },
  tapHint:          { fontSize: 11, color: Colors.textMuted, marginBottom: 8 },
  cleanBox:         { backgroundColor: '#e8f5e9', borderRadius: 12, padding: 14, borderWidth: 1, borderColor: '#4caf50' },
  cleanText:        { fontSize: 14, color: '#1b5e20', lineHeight: 22 },
  disclaimer:       { fontSize: 11, color: Colors.textMuted, textAlign: 'center', lineHeight: 16 },
});
